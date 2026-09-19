"""
TradePulse Signal Lifecycle & Outcome Tracker
Monitors active signals until trade expiry, evaluates real market exit prices,
determines WIN/LOSS/DRAW outcomes, records results to SQLite, and notifies subscribers.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from core.ingester.asset_registry import asset_registry
from core.models.candle import CandleStore
from core.models.signal import Signal
from core.storage.db import db

logger = logging.getLogger(__name__)


class SignalTracker:
    """Tracks active signals and evaluates real-time trade outcomes on expiry."""

    def __init__(
        self,
        candle_store: CandleStore,
        on_outcome_callback: Optional[Callable[[Signal], None]] = None,
        db_manager = None
    ):
        self.store = candle_store
        self.on_outcome = on_outcome_callback
        self.db = db_manager or db
        self.active_signals: Dict[str, Signal] = {}
        self.running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Starts background expiry monitoring loop."""
        if self.running:
            return
        self.running = True
        # Load any unresolved active signals from database
        for s in self.db.get_active_signals():
            self.active_signals[s.id] = s
        self._task = asyncio.create_task(self._expiry_loop())
        logger.info(f"[TRACKER] Signal lifecycle tracker started with {len(self.active_signals)} active signals.")

    def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()

    def register_signal(self, sig: Signal):
        """Registers a newly confirmed signal for lifecycle tracking."""
        self.active_signals[sig.id] = sig
        self.db.insert_signal(sig)
        logger.info(
            f"[TRACKER] Registered signal {sig.id[:8]} for {sig.asset_symbol} "
            f"({sig.direction} @ {sig.entry_price}) — Expiry in {sig.duration_minutes}m"
        )

    async def _expiry_loop(self):
        """Polls active signals every 1 second to evaluate outcomes right as expiry hits."""
        while self.running:
            try:
                await asyncio.sleep(1.0)
                now_ts = datetime.now(timezone.utc).timestamp()

                # Find signals whose expiry has passed
                expired_ids = [
                    sid for sid, sig in self.active_signals.items()
                    if sig.expiry_time and sig.expiry_time.timestamp() <= now_ts
                ]

                for sid in expired_ids:
                    sig = self.active_signals.pop(sid, None)
                    if sig:
                        self._resolve_signal(sig)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TRACKER] Expiry loop error: {e}")

    def _resolve_signal(self, sig: Signal):
        """Resolves trade outcome using genuine real-time market exit price with timeout protection."""
        # 1. Get real-time exit price from latest tick or latest candle close
        exit_price = asset_registry.get_latest_price(sig.asset_symbol)
        if exit_price is None or exit_price == 0.0:
            candles = self.store.get_candles(sig.asset_symbol, "1M")
            if candles:
                exit_price = candles[-1].close

        now_ts = datetime.now(timezone.utc).timestamp()
        expiry_ts = sig.expiry_time.timestamp() if sig.expiry_time else now_ts

        if exit_price is None or exit_price == 0.0:
            if (now_ts - expiry_ts) > 60.0:
                logger.warning(f"[TRACKER] Signal {sig.id[:8]} expired >60s ago without exit quote. Resolving DRAW.")
                outcome = "DRAW"
                exit_price = sig.entry_price
                sig.status = outcome
                sig.exit_price = exit_price
                self.db.update_signal_outcome(sig.id, outcome, exit_price)
                if self.on_outcome:
                    try:
                        self.on_outcome(sig)
                    except Exception as e:
                        logger.error(f"[TRACKER] Error in outcome callback: {e}")
                return
            logger.warning(f"[TRACKER] No live exit price available for {sig.asset_symbol}. Holding resolution.")
            self.active_signals[sig.id] = sig  # Retry on next tick
            return

        # 2. Evaluate WIN / LOSS / DRAW
        outcome = sig.evaluate_outcome(exit_price)
        logger.info(
            f"[TRACKER] Signal {sig.id[:8]} [{sig.asset_symbol}] EXPIRED: "
            f"Entry={sig.entry_price} ➔ Exit={exit_price} | Outcome: {outcome}"
        )

        # 3. Update SQLite database
        self.db.update_signal_outcome(sig.id, outcome, exit_price)

        # 4. Invoke callbacks (Telegram outcome notification + UI performance update)
        if self.on_outcome:
            try:
                self.on_outcome(sig)
            except Exception as e:
                logger.error(f"[TRACKER] Error in outcome callback: {e}")
