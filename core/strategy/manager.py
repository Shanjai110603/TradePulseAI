"""
TradePulse Strategy Manager
Manages user-defined custom strategies, persistence to ~/.tradepulse/strategies.json,
CRUD operations, enable/disable toggles, and JSON import/export.
"""
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import settings
from core.strategy.cooldown import cooldown_manager
from core.strategy.schema import UserStrategy

logger = logging.getLogger(__name__)


DEFAULT_STRATEGIES = [
    {
        "id": "strat_logus_trend",
        "name": "LOGU'S_TREND_STRATEGY",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 1,
        "min_payout": 80.0,
        "cooldown_seconds": 120,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.50, "max_opposing_wick": 0.30, "filter_preceding_doji": True, "filter_spike_multiplier": 2.5},
            "indicators": [],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_mtf_engulfing_1m",
        "name": "MTF_ENGULFING_1M",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 2,
        "min_payout": 80.0,
        "cooldown_seconds": 120,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.65, "max_opposing_wick": 0.30, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [],
            "price_action": {"require_engulfing": True, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_snr_wick_reversal",
        "name": "SNR_WICK_REVERSAL",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": False, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": False},
            "candle_anatomy": {"min_body_ratio": 0.10, "max_opposing_wick": 0.45, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "RSI", "period": 7, "condition": "BETWEEN", "min_val": 0, "max_val": 100},
                {"indicator": "BOLLINGER", "period": 20, "condition": "BETWEEN", "min_val": 0, "max_val": 1}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.05},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_ema_trend_bounce",
        "name": "EMA_TREND_BOUNCE",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.35, "max_opposing_wick": 0.35, "filter_preceding_doji": True, "filter_spike_multiplier": 2.8},
            "indicators": [
                {"indicator": "EMA", "period": 20, "condition": "BETWEEN", "min_val": 0, "max_val": 999999},
                {"indicator": "STOCHASTIC", "period": 14, "condition": "BETWEEN", "min_val": 0, "max_val": 100}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_mtf_momentum",
        "name": "MTF_MOMENTUM",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "3M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.70, "max_opposing_wick": 0.30, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "MACD", "period": 12, "condition": "BETWEEN", "min_val": -999999, "max_val": 999999},
                {"indicator": "EMA", "period": 50, "condition": "BETWEEN", "min_val": 0, "max_val": 999999}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": True, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    }
]
DEFAULT_STARTER_STRATEGY = DEFAULT_STRATEGIES[0]


class StrategyManager:
    """Loads, saves, and manages user-defined strategy profiles."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or (settings.resolved_data_dir / "strategies.json")
        self._lock = threading.Lock()
        self._strategies: Dict[str, UserStrategy] = {}
        self.load_strategies()

    def load_strategies(self):
        """Loads strategies from JSON or creates starter profile if file doesn't exist."""
        with self._lock:
            if not self.file_path.exists():
                logger.info(f"[STRATEGY] Creating starter templates at {self.file_path}")
                self._strategies = {s["id"]: UserStrategy(**s) for s in DEFAULT_STRATEGIES}
                self._save_to_disk_unlocked()
                return

            try:
                raw_text = self.file_path.read_text(encoding="utf-8")
                data = json.loads(raw_text)
                loaded: Dict[str, UserStrategy] = {}
                strat_list = data.get("strategies", []) if isinstance(data, dict) else data
                for s in strat_list:
                    obj = UserStrategy(**s)
                    loaded[obj.id] = obj

                # Auto-seed any missing default strategies
                changed = False
                for def_s in DEFAULT_STRATEGIES:
                    if def_s["id"] not in loaded:
                        obj = UserStrategy(**def_s)
                        loaded[obj.id] = obj
                        changed = True

                self._strategies = loaded
                if changed:
                    self._save_to_disk_unlocked()
                logger.info(f"[STRATEGY] Loaded {len(self._strategies)} strategies (including presets) from disk.")
            except Exception as e:
                logger.error(f"[STRATEGY] Error parsing strategies.json: {e}. Re-seeding starter templates.")
                self._strategies = {s["id"]: UserStrategy(**s) for s in DEFAULT_STRATEGIES}
                self._save_to_disk_unlocked()

    def _save_to_disk_unlocked(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if self.file_path.exists():
            bak_path = self.file_path.with_suffix(".json.bak")
            try:
                shutil.copy2(self.file_path, bak_path)
            except Exception as e:
                logger.warning(f"[STRATEGY] Failed to create backup file {bak_path}: {e}")

        payload = {
            "strategies": [s.model_dump() for s in self._strategies.values()]
        }
        tmp_path = self.file_path.with_suffix(".tmp")
        content = json.dumps(payload, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.file_path)

    def save_strategies(self):
        with self._lock:
            self._save_to_disk_unlocked()

    def get_all_strategies(self) -> List[UserStrategy]:
        with self._lock:
            return list(self._strategies.values())

    def get_active_strategies(self) -> List[UserStrategy]:
        with self._lock:
            return [s for s in self._strategies.values() if s.enabled]

    def get_strategy(self, strategy_id: str) -> Optional[UserStrategy]:
        with self._lock:
            return self._strategies.get(strategy_id)

    def save_or_update(self, strategy_data: Dict[str, Any]) -> UserStrategy:
        """Creates or updates a custom strategy."""
        with self._lock:
            strat = UserStrategy(**strategy_data)
            self._strategies[strat.id] = strat
            self._save_to_disk_unlocked()
            logger.info(f"[STRATEGY] Saved strategy '{strat.name}' (ID: {strat.id})")
            return strat

    def toggle_strategy(self, strategy_id: str, enabled: Optional[bool] = None) -> bool:
        with self._lock:
            if strategy_id in self._strategies:
                curr = self._strategies[strategy_id]
                curr.enabled = (not curr.enabled) if enabled is None else enabled
                self._save_to_disk_unlocked()
                return curr.enabled
            return False

    def delete_strategy(self, strategy_id: str) -> bool:
        with self._lock:
            if strategy_id in self._strategies:
                del self._strategies[strategy_id]
                self._save_to_disk_unlocked()
                cooldown_manager.clear_strategy(strategy_id)
                return True
            return False

    def export_json(self) -> str:
        with self._lock:
            payload = {"strategies": [s.model_dump() for s in self._strategies.values()]}
            return json.dumps(payload, indent=2)

    def import_json(self, raw_json: str) -> int:
        with self._lock:
            data = json.loads(raw_json)
            strat_list = data.get("strategies", []) if isinstance(data, dict) else data
            if not isinstance(strat_list, list):
                raise ValueError("Imported data must contain a list of strategies.")
            new_strategies: Dict[str, UserStrategy] = {}
            for s in strat_list:
                obj = UserStrategy(**s)
                new_strategies[obj.id] = obj

            for s_id, obj in new_strategies.items():
                self._strategies[s_id] = obj
            self._save_to_disk_unlocked()
            return len(new_strategies)


strategy_manager = StrategyManager()
