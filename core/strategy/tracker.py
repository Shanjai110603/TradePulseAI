"""
TradePulse Signal Lifecycle & Outcome Tracker
Monitors active signals until trade expiry, evaluates real market exit prices,
determines WIN/LOSS/DRAW outcomes, records results to SQLite, and notifies subscribers.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

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
        db_manager = None,
        sequential_trade_lock: bool = True,
        loss_cooldown_seconds: int = 120
    ):
        self.store = candle_store
        self.on_outcome = on_outcome_callback
        self.db = db_manager or db
        self.active_signals: Dict[str, Signal] = {}
        self.running = False
        self._task: Optional[asyncio.Task] = None

        # Sequential Live Trade Lock & Dynamic Cooldown
        self.sequential_trade_lock: bool = sequential_trade_lock
        self.loss_cooldown_seconds: int = loss_cooldown_seconds
        self.loss_cooldown_until: float = 0.0

    def is_trade_active(self, now_ts: Optional[float] = None) -> bool:
        """Returns True if there is currently an active, unexpired trade in progress."""
        now = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        for sig in self.active_signals.values():
            if sig.expiry_time and sig.expiry_time.timestamp() > now:
                return True
        return False

    def get_active_trade(self, now_ts: Optional[float] = None) -> Optional[Signal]:
        """Returns the most recent active live trade signal if any is in progress."""
        now = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        for sig in reversed(list(self.active_signals.values())):
            if sig.expiry_time and sig.expiry_time.timestamp() > now:
                return sig
        return None

    def can_dispatch_signal(self, now_ts: Optional[float] = None) -> Tuple[bool, str]:
        """
        Evaluates whether a new trade signal notification can be broadcast:
        1. When sequential_trade_lock is enabled, blocks if an existing trade is running until expiry.
        2. Blocks if inside the 2-minute post-loss cooldown.
        3. Unlocks immediately if previous trade was a profit/WIN.
        """
        if not self.sequential_trade_lock:
            return True, "Sequential trade lock disabled"

        now = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()

        # 1. Check if active trade is still in progress (waiting for expiry)
        active_sig = self.get_active_trade(now)
        if active_sig:
            exp_ts = active_sig.expiry_time.timestamp() if active_sig.expiry_time else now
            rem_sec = max(0, int(exp_ts - now))
            return False, f"Active trade in progress on {active_sig.asset_symbol} ({rem_sec}s until expiry)"

        # 2. Check if post-loss cooldown is active
        if now < self.loss_cooldown_until:
            rem_cd = int(self.loss_cooldown_until - now)
            return False, f"Post-loss cooldown active ({rem_cd}s remaining)"

        return True, "Ready for next trade signal"

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

    def register_signal(self, sig: Signal) -> bool:
        """
        Registers a newly confirmed live signal for lifecycle tracking.
        Guarantees only genuine, real-time live market signals are registered (no past/expired).
        """
        now_ts = datetime.now(timezone.utc).timestamp()

        # Reject already expired or historical backfill signals
        if sig.expiry_time and sig.expiry_time.timestamp() <= now_ts:
            logger.warning(f"[TRACKER] Discarded expired/historical signal for {sig.asset_symbol} (expired at {sig.expiry_time})")
            return False

        if sig.entry_time and (now_ts - sig.entry_time.timestamp()) > 90.0:
            logger.warning(f"[TRACKER] Discarded stale signal for {sig.asset_symbol} (>90s old)")
            return False

        self.active_signals[sig.id] = sig
        self.db.insert_signal(sig)
        logger.info(
            f"[TRACKER] Registered LIVE signal {sig.id[:8]} for {sig.asset_symbol} "
            f"({sig.direction} @ {sig.entry_price}) — Expiry in {sig.duration_minutes}m"
        )
        return True

    async def _expiry_loop(self):
        """Polls active signals every 1 second to evaluate outcomes right as expiry hits."""
        while self.running:
            try:
                await asyncio.sleep(1.0)
                now_ts = datetime.now(timezone.utc).timestamp()

                # Track price excursions (MFE/MAE) for all active signals
                for sig in self.active_signals.values():
                    curr_price = asset_registry.get_latest_price(sig.asset_symbol)
                    if curr_price and curr_price > 0:
                        audit = getattr(sig, "audit_trail", {})
                        if "high_during_trade" not in audit:
                            audit["high_during_trade"] = max(sig.entry_price, curr_price)
                            audit["low_during_trade"] = min(sig.entry_price, curr_price)
                        else:
                            audit["high_during_trade"] = max(audit["high_during_trade"], curr_price)
                            audit["low_during_trade"] = min(audit["low_during_trade"], curr_price)

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
                logger.debug(f"[TRACKER] Expiry loop error: {e}")

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

        # Compute MFE / MAE
        audit = getattr(sig, "audit_trail", {})
        high_p = audit.get("high_during_trade", max(sig.entry_price, exit_price))
        low_p = audit.get("low_during_trade", min(sig.entry_price, exit_price))
        if sig.is_call:
            mfe = round(max(0.0, high_p - sig.entry_price), 5)
            mae = round(max(0.0, sig.entry_price - low_p), 5)
        else:
            mfe = round(max(0.0, sig.entry_price - low_p), 5)
            mae = round(max(0.0, high_p - sig.entry_price), 5)

        sig.audit_trail["mfe"] = mfe
        sig.audit_trail["mae"] = mae

        # 2. Evaluate WIN / LOSS / DRAW
        outcome = sig.evaluate_outcome(exit_price)
        out_upper = str(outcome).upper()

        if "WIN" in out_upper:
            self.loss_cooldown_until = 0.0
            logger.info(f"🎉 [SEQUENTIAL TRADE] PROFIT / WIN on {sig.asset_symbol}. Next trade unlocked IMMEDIATELY.")
        elif "LOSS" in out_upper:
            self.loss_cooldown_until = now_ts + self.loss_cooldown_seconds
            logger.info(f"🛑 [SEQUENTIAL TRADE] LOSS on {sig.asset_symbol}. Engaging {self.loss_cooldown_seconds}s (2 min) cooldown before next trade.")
        else:
            self.loss_cooldown_until = 0.0
            logger.info(f"⚖️ [SEQUENTIAL TRADE] DRAW on {sig.asset_symbol}. Next trade unlocked IMMEDIATELY.")

        logger.info(
            f"[TRACKER] Signal {sig.id[:8]} [{sig.asset_symbol}] EXPIRED: "
            f"Entry={sig.entry_price} ➔ Exit={exit_price} | Outcome: {outcome} | MFE: {mfe} | MAE: {mae}"
        )

        # 3. Update SQLite database
        self.db.update_signal_outcome(sig.id, outcome, exit_price)

        # 4. Invoke callbacks (Telegram outcome notification + UI performance update)
        if self.on_outcome:
            try:
                self.on_outcome(sig)
            except Exception as e:
                logger.error(f"[TRACKER] Error in outcome callback: {e}")
