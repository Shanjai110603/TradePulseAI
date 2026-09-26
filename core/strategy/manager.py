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


# ==============================================================================
# STRATEGY DEFINITIONS & ARCHETYPE PROFILES
# ==============================================================================

# Primary algorithmic strategy for TradePulse Personal & 1M Real Market Forex
DUAL_BOLLINGER_PROTRUSION_STRATEGY = {
    "id": "strat_dual_bollinger_protrusion_1m",
    "name": "DUAL_BOLLINGER_PROTRUSION_1M",
    "enabled": True,
    "direction": "BOTH",
    "timeframe": "1M",
    "expiry_minutes": 1,
    "min_payout": 80.0,
    "cooldown_seconds": 120,
    "assets": ["ALL_MARKETS"],
    "filters": {
        "trend": {"enabled": False, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": False},
        "candle_anatomy": {"min_body_ratio": 0.20, "max_opposing_wick": 0.40, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
        "indicators": [
            {"indicator": "BOLLINGER", "period": 10, "condition": "BETWEEN", "min_val": 0, "max_val": 1},
            {"indicator": "BOLLINGER", "period": 13, "condition": "BETWEEN", "min_val": 0, "max_val": 1}
        ],
        "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.05},
        "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
    },
    "martingale_mtg1": False
}

# TradePulse Personal Edition: Isolated single-strategy default list
# Only the Dual Bollinger Protrusion 1M strategy is active on initial setup.
PERSONAL_DEFAULT_STRATEGIES = [DUAL_BOLLINGER_PROTRUSION_STRATEGY]

# TradePulse Standard Edition: Multi-strategy default catalog
DEFAULT_STRATEGIES = [
    DUAL_BOLLINGER_PROTRUSION_STRATEGY,
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
            "candle_anatomy": {"min_body_ratio": 0.15, "max_opposing_wick": 0.45, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
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
        "id": "strat_bollinger_mean_reversion",
        "name": "BOLLINGER_MEAN_REVERSION",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 2,
        "min_payout": 82.0,
        "cooldown_seconds": 150,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": False, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": False},
            "candle_anatomy": {"min_body_ratio": 0.25, "max_opposing_wick": 0.40, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "BOLLINGER", "period": 20, "condition": "BETWEEN", "min_val": 0, "max_val": 1},
                {"indicator": "RSI", "period": 14, "condition": "BETWEEN", "min_val": 20, "max_val": 80}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.05},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_bollinger_squeeze_breakout",
        "name": "BOLLINGER_SQUEEZE_BREAKOUT",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 2,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.65, "max_opposing_wick": 0.25, "filter_preceding_doji": True, "filter_spike_multiplier": 2.8},
            "indicators": [
                {"indicator": "BOLLINGER", "period": 20, "condition": "BETWEEN", "min_val": 0, "max_val": 1},
                {"indicator": "ATR", "period": 14, "condition": "BETWEEN", "min_val": 0.0001, "max_val": 999999}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": True, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_bollinger_rsi_confluence",
        "name": "BOLLINGER_RSI_CONFLUENCE",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 85.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": False, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": False},
            "candle_anatomy": {"min_body_ratio": 0.20, "max_opposing_wick": 0.45, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "BOLLINGER", "period": 20, "condition": "BETWEEN", "min_val": 0, "max_val": 1},
                {"indicator": "RSI", "period": 14, "condition": "BETWEEN", "min_val": 30, "max_val": 70}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.05},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": True
    },
    {
        "id": "strat_smc_order_block_sweep",
        "name": "SMC_ORDER_BLOCK_SWEEP",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 80.0,
        "cooldown_seconds": 240,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "15M", "ema_period": 50, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.40, "max_opposing_wick": 0.35, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": True, "liquidity_sweep_enabled": True, "bos_enabled": True, "order_block_enabled": True}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_breakout_momentum",
        "name": "BREAKOUT_MOMENTUM",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.70, "max_opposing_wick": 0.25, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "MACD", "period": 12, "condition": "BETWEEN", "min_val": -999999, "max_val": 999999},
                {"indicator": "ATR", "period": 14, "condition": "BETWEEN", "min_val": 0.0001, "max_val": 999999}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": True, "min_sr_clearance_pct": 0.15},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_supertrend_follower",
        "name": "SUPERTREND_TREND_FOLLOWER",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 2,
        "min_payout": 80.0,
        "cooldown_seconds": 120,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.60, "max_opposing_wick": 0.25, "filter_preceding_doji": True, "filter_spike_multiplier": 2.8},
            "indicators": [
                {"indicator": "SUPERTREND", "period": 10, "condition": "BULLISH"}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_sar_flip_sniper",
        "name": "PARABOLIC_SAR_FLIP_SNIPER",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 2,
        "min_payout": 80.0,
        "cooldown_seconds": 150,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": False, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": False},
            "candle_anatomy": {"min_body_ratio": 0.40, "max_opposing_wick": 0.35, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "PARABOLIC_SAR", "period": 14, "condition": "BULLISH"}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.05},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_ao_momentum_scalp",
        "name": "AWESOME_OSCILLATOR_SCALPER",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 1,
        "min_payout": 80.0,
        "cooldown_seconds": 120,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.55, "max_opposing_wick": 0.30, "filter_preceding_doji": True, "filter_spike_multiplier": 2.5},
            "indicators": [
                {"indicator": "AWESOME_OSCILLATOR", "period": 34, "condition": "BULLISH"}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_williams_extreme",
        "name": "WILLIAMS_R_EXTREME_SNIPER",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 82.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": False, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": False},
            "candle_anatomy": {"min_body_ratio": 0.30, "max_opposing_wick": 0.40, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "WILLIAMS_R", "period": 14, "condition": "BETWEEN", "min_val": -100, "max_val": 0}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.05},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_alligator_expansion",
        "name": "ALLIGATOR_EXPANSION_BREAKOUT",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.50, "max_opposing_wick": 0.30, "filter_preceding_doji": True, "filter_spike_multiplier": 2.8},
            "indicators": [
                {"indicator": "ALLIGATOR", "period": 13, "condition": "BULLISH"}
            ],
            "price_action": {"require_engulfing": True, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_keltner_breakout",
        "name": "KELTNER_DONCHIAN_BREAKOUT",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 2,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.65, "max_opposing_wick": 0.25, "filter_preceding_doji": True, "filter_spike_multiplier": 3.0},
            "indicators": [
                {"indicator": "KELTNER", "period": 20, "condition": "BETWEEN", "min_val": 0, "max_val": 999999}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": True, "min_sr_clearance_pct": 0.12},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_vortex_flow",
        "name": "VORTEX_FLOW_ALIGNMENT",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "5M",
        "expiry_minutes": 5,
        "min_payout": 80.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 20, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.50, "max_opposing_wick": 0.30, "filter_preceding_doji": True, "filter_spike_multiplier": 2.8},
            "indicators": [
                {"indicator": "VORTEX", "period": 14, "condition": "BULLISH"}
            ],
            "price_action": {"require_engulfing": False, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": False, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": False
    },
    {
        "id": "strat_ultra_confluence_pro",
        "name": "ULTRA_CONFLUENCE_PRO",
        "enabled": True,
        "direction": "BOTH",
        "timeframe": "1M",
        "expiry_minutes": 2,
        "min_payout": 85.0,
        "cooldown_seconds": 180,
        "assets": ["ALL_MARKETS"],
        "filters": {
            "trend": {"enabled": True, "mtf_timeframe": "5M", "ema_period": 50, "require_alignment": True},
            "candle_anatomy": {"min_body_ratio": 0.55, "max_opposing_wick": 0.30, "filter_preceding_doji": True, "filter_spike_multiplier": 2.5},
            "indicators": [
                {"indicator": "RSI", "period": 14, "condition": "BETWEEN", "min_val": 30, "max_val": 70},
                {"indicator": "EMA", "period": 20, "condition": "BETWEEN", "min_val": 0, "max_val": 999999}
            ],
            "price_action": {"require_engulfing": True, "require_sr_breakout": False, "min_sr_clearance_pct": 0.1},
            "smc": {"fvg_enabled": True, "liquidity_sweep_enabled": False, "bos_enabled": False, "order_block_enabled": False}
        },
        "martingale_mtg1": True
    }
]
DEFAULT_STARTER_STRATEGY = DEFAULT_STRATEGIES[0]


class StrategyManager:
    """Loads, saves, and manages user-defined strategy profiles."""

    def __init__(self, file_path: Optional[Path] = None):
        is_personal = os.environ.get("TRADEPULSE_PERSONAL") == "1"
        if file_path:
            self.file_path = file_path
        elif is_personal:
            self.file_path = settings.resolved_data_dir / "strategies_personal.json"
        else:
            self.file_path = settings.resolved_data_dir / "strategies.json"
        self._lock = threading.Lock()
        self._strategies: Dict[str, UserStrategy] = {}
        self.load_strategies()

    def load_strategies(self):
        """Loads strategies from JSON or creates default profile."""
        is_personal = os.environ.get("TRADEPULSE_PERSONAL") == "1"
        with self._lock:
            if not self.file_path.exists():
                if is_personal:
                    logger.info(f"[STRATEGY] Initializing Personal Edition strategy at {self.file_path}")
                    self._strategies = {s["id"]: UserStrategy(**s) for s in PERSONAL_DEFAULT_STRATEGIES}
                    self._save_to_disk_unlocked()
                    return
                else:
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

                if is_personal and not loaded:
                    # Seed personal strategy if empty
                    loaded = {s["id"]: UserStrategy(**s) for s in PERSONAL_DEFAULT_STRATEGIES}
                    self._strategies = loaded
                    self._save_to_disk_unlocked()
                    logger.info(f"[STRATEGY] Seeded {len(self._strategies)} personal strategy.")
                    return

                # Auto-seed default strategies for standard edition
                if not is_personal:
                    changed = False
                    for def_s in DEFAULT_STRATEGIES:
                        if def_s["id"] not in loaded:
                            obj = UserStrategy(**def_s)
                            loaded[obj.id] = obj
                            changed = True
                    if changed:
                        self._save_to_disk_unlocked()

                self._strategies = loaded
                logger.info(f"[STRATEGY] Loaded {len(self._strategies)} strategies from disk ({self.file_path.name}).")
            except Exception as e:
                logger.error(f"[STRATEGY] Error parsing strategies.json: {e}.")
                self._strategies = {s["id"]: UserStrategy(**s) for s in (PERSONAL_DEFAULT_STRATEGIES if is_personal else DEFAULT_STRATEGIES)}
                self._save_to_disk_unlocked()

    def clear_all_strategies(self):
        """Clears all strategies completely."""
        with self._lock:
            self._strategies.clear()
            self._save_to_disk_unlocked()
            try:
                cooldown_manager._cooldowns.clear()
            except Exception:
                pass
            logger.info(f"[STRATEGY] Cleared all strategies from {self.file_path.name}")

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
