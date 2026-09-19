"""
TradePulse SQLite Local Storage Module
Lightweight, thread-safe embedded persistence for signal history, outcomes,
win/loss metrics, and performance analytics.
"""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import settings
from core.models.signal import Signal


class Database:
    """Thread-safe SQLite client for local signals and analytics."""

    def __init__(self, db_path: Optional[Any] = None):
        self.db_path = db_path or (settings.resolved_data_dir / "tradepulse.db")
        self._is_memory = str(self.db_path) == ":memory:"
        self._lock = threading.Lock()
        
        # Single persistent connection guarded by self._lock (P2-2)
        if self._is_memory:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            # Enable WAL mode for high performance & safe concurrency
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns the thread-safe persistent connection."""
        return self._conn

    def close(self):
        """Closes the persistent SQLite connection cleanly."""
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"[DB] Error closing database connection: {e}")

    def _init_tables(self):
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT,
                    strategy_name TEXT,
                    asset_symbol TEXT,
                    direction TEXT,
                    timeframe TEXT,
                    duration_minutes INTEGER,
                    entry_price REAL,
                    entry_time TEXT,
                    expiry_time TEXT,
                    live_payout REAL,
                    confidence INTEGER,
                    status TEXT,
                    exit_price REAL,
                    audit_trail TEXT,
                    chart_image_path TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_asset ON signals(asset_symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT,
                    timestamp INTEGER,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    PRIMARY KEY (symbol, timestamp)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles(symbol, timestamp)")
            conn.commit()

    def insert_signal(self, sig: Signal):
        """Inserts a new confirmed active signal."""
        with self._lock, self._get_connection() as conn:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO signals (
                    id, strategy_id, strategy_name, asset_symbol, direction,
                    timeframe, duration_minutes, entry_price, entry_time,
                    expiry_time, live_payout, confidence, status, exit_price,
                    audit_trail, chart_image_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sig.id, sig.strategy_id, sig.strategy_name, sig.asset_symbol, sig.direction,
                sig.timeframe, sig.duration_minutes, sig.entry_price,
                sig.entry_time.isoformat() if sig.entry_time else None,
                sig.expiry_time.isoformat() if sig.expiry_time else None,
                sig.live_payout, sig.confidence, sig.status, sig.exit_price,
                json.dumps(sig.audit_trail), sig.chart_image_path, now_iso
            ))
            conn.commit()

    def update_signal_outcome(self, signal_id: str, status: str, exit_price: float):
        """Updates outcome status (WIN/LOSS/DRAW) and exit price."""
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                UPDATE signals
                SET status = ?, exit_price = ?
                WHERE id = ?
            """, (status, exit_price, signal_id))
            conn.commit()

    def get_recent_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent signals list."""
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM signals
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_active_signals(self) -> List[Signal]:
        """Returns currently active unresolved signals."""
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM signals
                WHERE status = 'ACTIVE'
            """).fetchall()

            signals = []
            for r in rows:
                entry_dt = datetime.fromisoformat(r["entry_time"]) if r["entry_time"] else datetime.now(timezone.utc)
                expiry_dt = datetime.fromisoformat(r["expiry_time"]) if r["expiry_time"] else None
                s = Signal(
                    id=r["id"],
                    strategy_id=r["strategy_id"],
                    strategy_name=r["strategy_name"],
                    asset_symbol=r["asset_symbol"],
                    direction=r["direction"],
                    timeframe=r["timeframe"],
                    duration_minutes=r["duration_minutes"],
                    entry_price=r["entry_price"],
                    entry_time=entry_dt,
                    expiry_time=expiry_dt,
                    live_payout=r["live_payout"],
                    confidence=r["confidence"],
                    status=r["status"],
                    exit_price=r["exit_price"],
                    audit_trail=json.loads(r["audit_trail"] or "{}"),
                    chart_image_path=r["chart_image_path"]
                )
                signals.append(s)
            return signals

    def get_performance_stats(self) -> Dict[str, Any]:
        """Calculates win rate, total count, wins, losses, draws, and per-strategy/asset breakdown."""
        with self._lock, self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM signals WHERE status != 'ACTIVE'").fetchone()[0]
            wins = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'WIN'").fetchone()[0]
            losses = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'LOSS'").fetchone()[0]
            draws = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'DRAW'").fetchone()[0]

            win_rate = (wins / total * 100.0) if total > 0 else 0.0

            # Strategy breakdown
            strat_rows = conn.execute("""
                SELECT strategy_id, strategy_name,
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN status = 'LOSS' THEN 1 ELSE 0 END) as losses
                FROM signals
                WHERE status != 'ACTIVE'
                GROUP BY strategy_id, strategy_name
                ORDER BY wins DESC, total DESC
            """).fetchall()

            strategy_breakdown = []
            for sr in strat_rows:
                s_tot = sr["total"]
                s_win = sr["wins"] or 0
                s_loss = sr["losses"] or 0
                s_wr = round((s_win / s_tot * 100.0), 1) if s_tot > 0 else 0.0
                strategy_breakdown.append({
                    "strategy_id": sr["strategy_id"],
                    "strategy_name": sr["strategy_name"],
                    "total": s_tot,
                    "wins": s_win,
                    "losses": s_loss,
                    "win_rate": s_wr
                })

            # Asset breakdown (top pairs)
            asset_rows = conn.execute("""
                SELECT asset_symbol,
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN status = 'LOSS' THEN 1 ELSE 0 END) as losses
                FROM signals
                WHERE status != 'ACTIVE'
                GROUP BY asset_symbol
                HAVING total >= 1
                ORDER BY wins DESC, total DESC
                LIMIT 10
            """).fetchall()

            top_pairs = []
            for ar in asset_rows:
                a_tot = ar["total"]
                a_win = ar["wins"] or 0
                a_loss = ar["losses"] or 0
                a_wr = round((a_win / a_tot * 100.0), 1) if a_tot > 0 else 0.0
                top_pairs.append({
                    "symbol": ar["asset_symbol"],
                    "total": a_tot,
                    "wins": a_win,
                    "losses": a_loss,
                    "win_rate": a_wr
                })

            return {
                "total_signals": total,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": round(win_rate, 1),
                "strategy_breakdown": strategy_breakdown,
                "top_pairs": top_pairs
            }

    def get_strategy_performance_stats(self, strategy_id: str) -> Dict[str, Any]:
        """Calculates win rate and trade counts for a specific strategy."""
        with self._lock, self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE strategy_id = ? AND status != 'ACTIVE'",
                (strategy_id,)
            ).fetchone()[0]
            wins = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE strategy_id = ? AND status = 'WIN'",
                (strategy_id,)
            ).fetchone()[0]
            losses = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE strategy_id = ? AND status = 'LOSS'",
                (strategy_id,)
            ).fetchone()[0]
            draws = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE strategy_id = ? AND status = 'DRAW'",
                (strategy_id,)
            ).fetchone()[0]

            win_rate = (wins / total * 100.0) if total > 0 else 0.0
            return {
                "total_signals": total,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": round(win_rate, 1)
            }

    def insert_candle(self, symbol: str, candle: Any):
        """Persists a completed 1-minute candle."""
        if not candle or getattr(candle, 'timestamp', -1) < 0:
            return
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO candles (symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (symbol, int(candle.timestamp), float(candle.open), float(candle.high),
                  float(candle.low), float(candle.close), float(candle.volume)))
            conn.commit()

    def insert_candles_batch(self, symbol: str, candles: List[Any]):
        """Persists multiple completed 1-minute candles in a single transaction."""
        valid_candles = [c for c in (candles or []) if getattr(c, 'timestamp', -1) >= 0]
        if not valid_candles:
            return
        with self._lock, self._get_connection() as conn:
            params = [
                (symbol, int(c.timestamp), float(c.open), float(c.high), float(c.low), float(c.close), float(c.volume))
                for c in valid_candles
            ]
            conn.executemany("""
                INSERT OR REPLACE INTO candles (symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, params)
            conn.commit()

    def get_recent_candles(self, symbol: str, limit: int = 300) -> List[Any]:
        """Loads the most recent completed 1-minute candles for a symbol from SQLite."""
        from core.models.candle import Candle
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("""
                SELECT timestamp, open, high, low, close, volume
                FROM candles
                WHERE symbol = ? AND timestamp >= 0
                ORDER BY timestamp DESC
                LIMIT ?
            """, (symbol, limit))
            rows = cur.fetchall()
            return [
                Candle(
                    timestamp=r["timestamp"],
                    open=r["open"],
                    high=r["high"],
                    low=r["low"],
                    close=r["close"],
                    volume=r["volume"]
                )
                for r in reversed(rows)
            ]


db = Database()
