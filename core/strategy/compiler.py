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

        # Dedicated strategy archetypes apply to built-in presets
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
        elif strat_id_lower in ("strat_bollinger_mean_reversion", "strat_bollinger_mean", "bollinger_mean"):
            return {
                "operator": "AND",
                "conditions": [{"type": "bollinger_mean_reversion", "params": {}}]
            }
        elif strat_id_lower in ("strat_bollinger_squeeze_breakout", "strat_bollinger_squeeze", "bollinger_squeeze"):
            return {
                "operator": "AND",
                "conditions": [{"type": "bollinger_squeeze_breakout", "params": {}}]
            }
        elif strat_id_lower in ("strat_bollinger_rsi_confluence", "strat_bollinger_rsi", "bollinger_rsi"):
            return {
                "operator": "AND",
                "conditions": [{"type": "bollinger_rsi_confluence", "params": {}}]
            }
        elif strat_id_lower in ("strat_dual_bollinger_protrusion_1m", "strat_dual_bb_protrusion") or any(
            (getattr(i, "indicator", "") or "").upper() in ("DUAL_BOLLINGER_PROTRUSION", "DUAL_BB") for i in getattr(strategy.filters, "indicators", [])
        ):
            # Compile dedicated AST execution node for the Dual Bollinger Band Protrusion Reversal Strategy:
            # - Evaluates Bollinger Bands (default 10 & 13) with standard deviation (default 2.0)
            # - Enforces minimum body protrusion (default 20%) beyond outer envelope
            # - Enforces market regime check (immediate in consolidation vs S/R confluence in trends)
            bb_ind = next((i for i in getattr(strategy.filters, "indicators", []) if (getattr(i, "indicator", "") or "").upper() in ("BOLLINGER", "DUAL_BOLLINGER_PROTRUSION", "DUAL_BB")), None)
            bb_params = getattr(bb_ind, "params", {}) or {} if bb_ind else {}
            p1 = int(bb_params.get("period_1", getattr(bb_ind, "period", 10) if bb_ind else 10))
            p2 = int(bb_params.get("period_2", 13))
            dev = float(bb_params.get("deviation", 2.0))
            min_prot = float(bb_params.get("min_body_protrusion", 0.20))
            return {
                "operator": "AND",
                "conditions": [{
                    "type": "dual_bollinger_protrusion",
                    "params": {
                        "period_1": p1,
                        "period_2": p2,
                        "deviation": dev,
                        "min_body_protrusion": min_prot,
                        "require_box_or_sr": True
                    }
                }]
            }

        root_conditions = []
        filters = strategy.filters

        # 1. Candle Anatomy Rules
        anatomy = filters.candle_anatomy
        anatomy_params = {
            "min_body_ratio": anatomy.min_body_ratio,
            "max_opposing_wick": anatomy.max_opposing_wick,
            "filter_preceding_doji": anatomy.filter_preceding_doji,
            "filter_spike_multiplier": anatomy.filter_spike_multiplier,
        }
        if getattr(anatomy, "min_rejection_wick_ratio", 0.0) > 0:
            anatomy_params["min_rejection_wick_ratio"] = anatomy.min_rejection_wick_ratio
        root_conditions.append({
            "type": "candle_anatomy",
            "params": anatomy_params
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
            ind_params = {
                "indicator": ind.indicator,
                "period": ind.period,
                "condition": ind.condition,
                "min_val": ind.min_val,
                "max_val": ind.max_val,
                "field": getattr(ind, "field", None),
            }
            if getattr(ind, "params", None):
                ind_params.update(ind.params)
            root_conditions.append({
                "type": "indicator_threshold",
                "params": ind_params
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

        confluence = getattr(filters, "confluence", None)
        if confluence and getattr(confluence, "enabled", False):
            return {
                "operator": "CONFLUENCE_VOTING",
                "min_agreeing": int(getattr(confluence, "min_agreeing_indicators", 2)),
                "min_quality_score": float(getattr(confluence, "min_quality_score", 75.0)),
                "conditions": root_conditions
            }

        return {
            "operator": "AND",
            "conditions": root_conditions
        }
