"""
TradePulse Anti-Spam Cooldown & Deduplication Manager
Prevents repetitive Telegram and in-app alerts on consecutive candles for the same asset.
"""
import time
from typing import Dict, Tuple, Optional


class CooldownManager:
    """Tracks per-strategy, per-asset cooldown windows and candle timestamps."""

    def __init__(self):
        # Key: (strategy_id, asset_symbol) -> last_fired_unix_ts
        self._cooldowns: Dict[Tuple[str, str], float] = {}
        # Key: (strategy_id, asset_symbol) -> last_candle_timestamp
        self._last_candle_ts: Dict[Tuple[str, str], int] = {}
        self.global_cooldown_seconds: Optional[int] = None

    def set_global_cooldown(self, seconds: int):
        """Sets an overarching global cooldown period in seconds for all strategies."""
        self.global_cooldown_seconds = max(10, int(seconds))

    def is_allowed(
        self,
        strategy_id: str,
        asset_symbol: str,
        candle_timestamp: int,
        cooldown_seconds: int = 180
    ) -> bool:
        """
        Returns True if a signal can fire; False if in cooldown or duplicate candle.
        """
        effective_cooldown = self.global_cooldown_seconds if self.global_cooldown_seconds is not None else cooldown_seconds
        key = (strategy_id, asset_symbol)
        now = time.time()

        # 1. Reject duplicate candle (signal already fired on this exact closed candle)
        if self._last_candle_ts.get(key) == candle_timestamp:
            return False

        # 2. Check time window cooldown
        last_fired = self._cooldowns.get(key, 0.0)
        if (now - last_fired) < effective_cooldown:
            return False

        return True

    def record_signal(self, strategy_id: str, asset_symbol: str, candle_timestamp: int):
        """Records that a signal fired to engage the cooldown window."""
        key = (strategy_id, asset_symbol)
        self._cooldowns[key] = time.time()
        self._last_candle_ts[key] = candle_timestamp

    def reset_cooldown(self, strategy_id: str, asset_symbol: str):
        key = (strategy_id, asset_symbol)
        self._cooldowns.pop(key, None)
        self._last_candle_ts.pop(key, None)

    def clear_strategy(self, strategy_id: str):
        """Removes all cooldown and candle records for a deleted strategy (P5-1)."""
        stale_keys = [k for k in self._cooldowns.keys() if k[0] == strategy_id]
        for k in stale_keys:
            self._cooldowns.pop(k, None)
            self._last_candle_ts.pop(k, None)

    def prune(self, max_age_seconds: float = 86400):
        """Prunes tracking entries older than max_age_seconds (P5-1)."""
        now = time.time()
        stale_keys = [k for k, ts in self._cooldowns.items() if (now - ts) > max_age_seconds]
        for k in stale_keys:
            self._cooldowns.pop(k, None)
            self._last_candle_ts.pop(k, None)


cooldown_manager = CooldownManager()

