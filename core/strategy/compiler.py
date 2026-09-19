"""
TradePulse Visual Strategy to AST Compiler
Translates high-level declarative UserStrategy configurations (from UI/JSON)
into optimized recursive AST condition trees for PatternRuleEngine execution.
"""
from typing import Any, Dict
from core.strategy.schema import UserStrategy


class StrategyCompiler:
    """Compiles high-level UserStrategy models into executable AST condition trees."""

    @staticmethod
    def compile_strategy_ast(strategy: UserStrategy) -> Dict[str, Any]:
        """
        Compiles a UserStrategy into a master root AST node:
        {
            "operator": "AND",
            "conditions": [...]
        }
        """
        strat_id_lower = strategy.id.lower()
        filters = strategy.filters
        has_custom_indicators = bool(filters.indicators)
        has_custom_smc = (
            filters.smc.fvg_enabled
            or filters.smc.liquidity_sweep_enabled
            or filters.smc.bos_enabled
            or filters.smc.order_block_enabled
        )

        # Dedicated strategy archetypes apply to built-in presets unless custom indicators or SMC are configured
        if not has_custom_indicators and not has_custom_smc:
            if strat_id_lower == "strat_logus_trend":
                return {
                    "operator": "AND",
                    "conditions": [{"type": "logus_trend", "params": {}}]
                }
            elif strat_id_lower == "strat_mtf_engulfing_1m":
                return {
                    "operator": "AND",
                    "conditions": [{"type": "mtf_engulfing_1m", "params": {"min_body_ratio": filters.candle_anatomy.min_body_ratio or 0.65}}]
                }
            elif strat_id_lower == "strat_snr_wick_reversal":
                return {
                    "operator": "AND",
                    "conditions": [{"type": "snr_wick_reversal", "params": {"min_wick_ratio": filters.candle_anatomy.max_opposing_wick or 0.45}}]
                }
            elif strat_id_lower == "strat_ema_trend_bounce":
                return {
                    "operator": "AND",
                    "conditions": [{"type": "ema_trend_bounce", "params": {}}]
                }
            elif strat_id_lower == "strat_mtf_momentum":
                return {
                    "operator": "AND",
                    "conditions": [{"type": "mtf_momentum", "params": {}}]
                }

        root_conditions = []
        filters = strategy.filters

        # 1. Candle Anatomy Rules
        anatomy = filters.candle_anatomy
        root_conditions.append({
            "type": "candle_anatomy",
            "params": {
                "min_body_ratio": anatomy.min_body_ratio,
                "max_opposing_wick": anatomy.max_opposing_wick,
                "filter_preceding_doji": anatomy.filter_preceding_doji,
                "filter_spike_multiplier": anatomy.filter_spike_multiplier,
            }
        })

        # 2. Price Action / Engulfing Rules
        pa = filters.price_action
        if pa.require_engulfing or filters.trend.enabled:
            root_conditions.append({
                "type": "mtf_engulfing",
                "params": {
                    "require_engulfing": pa.require_engulfing,
                    "mtf_enabled": filters.trend.enabled,
                    "mtf_timeframe": filters.trend.mtf_timeframe,
                    "ema_period": filters.trend.ema_period,
                }
            })

        if pa.min_sr_clearance_pct > 0:
            root_conditions.append({
                "type": "sr_clearance",
                "params": {
                    "min_clearance_pct": pa.min_sr_clearance_pct / 100.0
                }
            })

        # 3. Indicators Rules
        for ind in filters.indicators:
            root_conditions.append({
                "type": "indicator_threshold",
                "params": {
                    "indicator": ind.indicator,
                    "period": ind.period,
                    "condition": ind.condition,
                    "min_val": ind.min_val,
                    "max_val": ind.max_val,
                    "field": getattr(ind, "field", None),
                }
            })

        # 4. Smart Money Concepts (SMC)
        smc = filters.smc
        if smc.fvg_enabled:
            root_conditions.append({"type": "fair_value_gap", "params": {}})
        if smc.liquidity_sweep_enabled:
            root_conditions.append({"type": "liquidity_sweep", "params": {"lookback": 5}})
        if smc.bos_enabled:
            root_conditions.append({"type": "break_of_structure", "params": {"lookback": 5}})
        if smc.order_block_enabled:
            root_conditions.append({"type": "order_block", "params": {}})

        return {
            "operator": "AND",
            "conditions": root_conditions
        }
