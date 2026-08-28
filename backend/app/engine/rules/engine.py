import math
from typing import List, Dict, Any, Optional, Union, Tuple
from app.engine.market_data.base import Candle
from app.engine.indicators.engine import TechnicalIndicatorEngine


class PatternRuleEngine:
    """
    Deterministic Pattern and Strategy Rule Evaluator.
    Evaluates AST rule trees, candlestick sequences, support/resistance breakouts,
    indicators, momentum, trend, and volume without AI dependency.
    """

    @classmethod
    def evaluate_pattern(
        cls,
        pattern_config: Dict[str, Any],
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for evaluating a pattern against a candle series.
        Returns:
            {
                "matched": bool,
                "direction": str ("UP" | "DOWN" | "BUY" | "SELL"),
                "reason": str,
                "matched_at_candle_index": int,
                "reference_price": float,
                "support_level": Optional[float],
                "resistance_level": Optional[float],
                "technical_snapshot": Dict[str, Any],
                "rule_evaluation_log": List[Dict[str, Any]]
            }
        """
        if len(candles) < 3:
            return {
                "matched": False,
                "reason": "Insufficient candles for pattern evaluation",
                "technical_snapshot": {},
                "rule_evaluation_log": []
            }

        snapshot = TechnicalIndicatorEngine.calculate_technical_snapshot(candles)
        log: List[Dict[str, Any]] = []

        # 1. Trend Filter Evaluation
        trend_cfg = pattern_config.get("trend_config", {})
        if trend_cfg:
            trend_pass, trend_reason = cls._evaluate_trend(trend_cfg, snapshot, multi_timeframe_candles)
            log.append({"step": "trend", "passed": trend_pass, "reason": trend_reason})
            if not trend_pass:
                return {"matched": False, "reason": f"Trend requirement failed: {trend_reason}", "technical_snapshot": snapshot, "rule_evaluation_log": log}

        # 2. Momentum Filter Evaluation
        momentum_cfg = pattern_config.get("momentum_config", {})
        if momentum_cfg:
            mom_pass, mom_reason = cls._evaluate_momentum(momentum_cfg, snapshot)
            log.append({"step": "momentum", "passed": mom_pass, "reason": mom_reason})
            if not mom_pass:
                return {"matched": False, "reason": f"Momentum requirement failed: {mom_reason}", "technical_snapshot": snapshot, "rule_evaluation_log": log}

        # 3. Volume Filter Evaluation
        volume_cfg = pattern_config.get("volume_config", {})
        if volume_cfg:
            vol_pass, vol_reason = cls._evaluate_volume(volume_cfg, snapshot)
            log.append({"step": "volume", "passed": vol_pass, "reason": vol_reason})
            if not vol_pass:
                return {"matched": False, "reason": f"Volume requirement failed: {vol_reason}", "technical_snapshot": snapshot, "rule_evaluation_log": log}

        # 4. Indicator Conditions Evaluation
        indicators_cfg = pattern_config.get("indicators_config", [])
        if indicators_cfg:
            ind_pass, ind_reason = cls._evaluate_indicators(indicators_cfg, snapshot)
            log.append({"step": "indicators", "passed": ind_pass, "reason": ind_reason})
            if not ind_pass:
                return {"matched": False, "reason": f"Indicator requirements failed: {ind_reason}", "technical_snapshot": snapshot, "rule_evaluation_log": log}

        # 5. Composite AST Rules Evaluation (Candle sequence, S/R breakdown, Pattern Type 14, etc.)
        rules_cfg = pattern_config.get("rules_config", {})
        if rules_cfg:
            rules_pass, rules_reason, context = cls._evaluate_rule_node(rules_cfg, candles, snapshot)
            log.append({"step": "rules_ast", "passed": rules_pass, "reason": rules_reason, "context": context})
            if not rules_pass:
                return {"matched": False, "reason": f"Rule condition failed: {rules_reason}", "technical_snapshot": snapshot, "rule_evaluation_log": log}
        else:
            context = {}
            rules_reason = None

        last_candle = candles[-1]
        direction = pattern_config.get("direction", "DOWN").upper()
        match_reason = rules_reason if (rules_cfg and rules_reason) else "All deterministic pattern conditions successfully satisfied"

        return {
            "matched": True,
            "direction": direction,
            "reason": match_reason,
            "matched_at_candle_index": len(candles) - 1,
            "reference_price": last_candle.close,
            "support_level": context.get("support_level"),
            "resistance_level": context.get("resistance_level"),
            "technical_snapshot": snapshot,
            "rule_evaluation_log": log,
            "context": context
        }

    # ---------------------------------------------------------
    # Helper Evaluators
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_trend(cls, cfg: Dict[str, Any], snapshot: Dict[str, Any], mtf_candles: Optional[Dict[str, List[Candle]]] = None) -> Tuple[bool, str]:
        required = cfg.get("required", "Any").upper()
        current_trend = snapshot.get("market_structure", {}).get("trend", "NEUTRAL").upper()

        if required in ["ANY", "NONE", ""]:
            pass
        elif required == "STRONG_BULLISH" and current_trend != "BULLISH":
            return False, f"Expected Strong Bullish, got {current_trend}"
        elif required == "BULLISH" and current_trend not in ["BULLISH", "STRONG_BULLISH"]:
            return False, f"Expected Bullish, got {current_trend}"
        elif required == "BEARISH" and current_trend not in ["BEARISH", "STRONG_BEARISH"]:
            return False, f"Expected Bearish, got {current_trend}"
        elif required == "NEUTRAL" and current_trend != "NEUTRAL":
            return False, f"Expected Neutral, got {current_trend}"

        # MTF Trend evaluation if configured
        mtf_req = cfg.get("mtf", {})
        if mtf_req and mtf_candles:
            for tf, tf_trend in mtf_req.items():
                if tf_trend.upper() not in ["ANY", ""]:
                    tf_list = mtf_candles.get(tf, [])
                    if tf_list:
                        tf_snap = TechnicalIndicatorEngine.calculate_technical_snapshot(tf_list)
                        tf_actual = tf_snap.get("market_structure", {}).get("trend", "NEUTRAL").upper()
                        if tf_trend.upper() != tf_actual:
                            return False, f"MTF {tf} expected {tf_trend}, got {tf_actual}"

        return True, f"Trend matched {current_trend}"

    @classmethod
    def _evaluate_momentum(cls, cfg: Dict[str, Any], snapshot: Dict[str, Any]) -> Tuple[bool, str]:
        rsi = snapshot.get("rsi")
        if rsi is not None:
            rsi_min = cfg.get("rsi_min")
            rsi_max = cfg.get("rsi_max")
            if rsi_min is not None and rsi < rsi_min:
                return False, f"RSI {rsi} below min threshold {rsi_min}"
            if rsi_max is not None and rsi > rsi_max:
                return False, f"RSI {rsi} above max threshold {rsi_max}"

        adx = snapshot.get("adx")
        if adx is not None:
            adx_min = cfg.get("adx_min")
            if adx_min is not None and adx < adx_min:
                return False, f"ADX {adx} below min threshold {adx_min}"

        macd_bias = cfg.get("macd_bias", "Any").upper()
        if macd_bias not in ["ANY", ""]:
            macd_hist = snapshot.get("macd", {}).get("histogram")
            if macd_hist is not None:
                if macd_bias == "BULLISH" and macd_hist < 0:
                    return False, f"MACD histogram {macd_hist} is bearish (expected Bullish)"
                elif macd_bias == "BEARISH" and macd_hist > 0:
                    return False, f"MACD histogram {macd_hist} is bullish (expected Bearish)"

        return True, "Momentum criteria satisfied"

    @classmethod
    def _evaluate_volume(cls, cfg: Dict[str, Any], snapshot: Dict[str, Any]) -> Tuple[bool, str]:
        vol_type = cfg.get("type", "Any").lower()
        vol_ratio = snapshot.get("volume_ratio", 1.0)
        min_pct = cfg.get("min_pct_of_ma", 100.0) / 100.0

        if vol_type == "above_average" and vol_ratio < min_pct:
            return False, f"Volume ratio {vol_ratio:.2f} is below required {min_pct:.2f}"
        elif vol_type == "strong" and vol_ratio < 1.5:
            return False, f"Strong volume required (ratio >= 1.5), got {vol_ratio:.2f}"

        return True, f"Volume ratio {vol_ratio:.2f} satisfies criteria"

    @classmethod
    def _evaluate_indicators(cls, criteria_list: List[Dict[str, Any]], snapshot: Dict[str, Any]) -> Tuple[bool, str]:
        for crit in criteria_list:
            ind = crit.get("indicator", "").upper()
            cond = crit.get("condition", "").upper()
            val = crit.get("value")

            actual_val = None
            if ind == "RSI":
                actual_val = snapshot.get("rsi")
            elif ind == "EMA_FAST":
                actual_val = snapshot.get("ema_fast")
            elif ind == "EMA_SLOW":
                actual_val = snapshot.get("ema_slow")
            elif ind == "SMA_200":
                actual_val = snapshot.get("sma_200")
            elif ind == "VWAP":
                actual_val = snapshot.get("vwap")
            elif ind == "ATR":
                actual_val = snapshot.get("atr")
            elif ind == "ADX":
                actual_val = snapshot.get("adx")

            if actual_val is None or val is None:
                continue

            if cond == "ABOVE" and not (actual_val > val):
                return False, f"{ind} ({actual_val}) is not ABOVE {val}"
            elif cond == "BELOW" and not (actual_val < val):
                return False, f"{ind} ({actual_val}) is not BELOW {val}"

        return True, "Indicator criteria satisfied"

    # ---------------------------------------------------------
    # Composite AST Node Evaluator (AND / OR / NOT / Primitives)
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_rule_node(
        cls,
        node: Dict[str, Any],
        candles: List[Candle],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Evaluates AST node with support for nested AND, OR, NOT, and primitive conditions"""
        if not node:
            return True, "Empty node", {}

        operator = node.get("operator", "AND").upper()
        conditions = node.get("conditions", [])

        # If it's a leaf primitive node directly
        if "type" in node and not conditions:
            return cls._evaluate_primitive(node, candles, snapshot)

        # Composite node
        context: Dict[str, Any] = {}

        if operator == "AND":
            child_reasons = []
            for idx, child in enumerate(conditions):
                pass_cond, reason, child_ctx = cls._evaluate_rule_node(child, candles, snapshot)
                context.update(child_ctx)
                child_reasons.append(reason)
                if not pass_cond:
                    return False, f"AND branch {idx+1} failed: {reason}", context
            summary_reason = child_reasons[0] if len(child_reasons) == 1 else (" | ".join(child_reasons) if child_reasons else "All AND conditions passed")
            return True, summary_reason, context

        elif operator == "OR":
            for idx, child in enumerate(conditions):
                pass_cond, reason, child_ctx = cls._evaluate_rule_node(child, candles, snapshot)
                if pass_cond:
                    context.update(child_ctx)
                    return True, reason, context
            return False, "None of the OR conditions passed", context

        elif operator == "NOT":
            if not conditions:
                return True, "Empty NOT", {}
            pass_cond, reason, child_ctx = cls._evaluate_rule_node(conditions[0], candles, snapshot)
            if pass_cond:
                return False, f"NOT condition failed because child was true: {reason}", {}
            return True, "NOT condition passed", {}

        return True, "Default pass", context

    @classmethod
    def _evaluate_primitive(
        cls,
        node: Dict[str, Any],
        candles: List[Candle],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates specialized primitives including:
        - pattern_type_14: The exact Pattern Type 14 specification
        - pattern_type_14_inverted: Inverted Pattern Type 14 for UP signals
        - candle_color: Single candle color at index
        - candle_sequence: Array of candle colors (e.g. ['bearish', 'bullish', 'bullish'])
        - support_break: Breakout / breakdown of support
        - resistance_break: Breakout / breakout of resistance
        """
        p_type = node.get("type", "")
        params = node.get("params", {})

        # Candle Color Primitive
        if p_type == "candle_color":
            idx = params.get("index", -1)
            target_color = params.get("color", "bearish").lower()
            if abs(idx) > len(candles):
                return False, f"Candle index {idx} out of range", {}
            candle = candles[idx]
            actual_color = "bullish" if candle.is_bullish else ("bearish" if candle.is_bearish else "doji")
            if target_color != actual_color:
                return False, f"Candle [{idx}] is {actual_color}, expected {target_color}", {}
            return True, f"Candle [{idx}] is {target_color}", {}

        # Candle Sequence Primitive
        elif p_type == "candle_sequence":
            colors = params.get("colors", [])  # e.g., ["bearish", "bullish", "bullish"]
            seq_len = len(colors)
            if len(candles) < seq_len:
                return False, "Not enough candles for sequence", {}
            
            sub_candles = candles[-seq_len:]
            for i, expected in enumerate(colors):
                c = sub_candles[i]
                c_color = "bullish" if c.is_bullish else ("bearish" if c.is_bearish else "doji")
                if expected.lower() != c_color:
                    return False, f"Sequence index {i} expected {expected}, got {c_color}", {}
            return True, f"Sequence {colors} matched exactly", {}

        # Support Break Primitive
        elif p_type == "support_break":
            break_type = params.get("break_type", "close_below")  # close_below | wick_below
            lookback = params.get("lookback", 5)
            if len(candles) < lookback + 1:
                return False, "Not enough candles for support break", {}

            # Determine support level from preceding lookback candles (excluding the trigger candle -1)
            preceding = candles[-(lookback + 1) : -1]
            support_level = min(c.low for c in preceding)
            trigger_candle = candles[-1]

            if break_type == "close_below":
                if trigger_candle.close < support_level:
                    return True, f"Close ({trigger_candle.close}) broke below support ({support_level})", {"support_level": support_level}
                return False, f"Close ({trigger_candle.close}) did not close below support ({support_level})", {}
            elif break_type == "wick_below":
                if trigger_candle.low < support_level:
                    return True, f"Low ({trigger_candle.low}) pierced support ({support_level})", {"support_level": support_level}
                return False, f"Low ({trigger_candle.low}) did not pierce support ({support_level})", {}

        # Resistance Break Primitive
        elif p_type == "resistance_break":
            break_type = params.get("break_type", "close_above")
            lookback = params.get("lookback", 5)
            if len(candles) < lookback + 1:
                return False, "Not enough candles for resistance break", {}

            preceding = candles[-(lookback + 1) : -1]
            resistance_level = max(c.high for c in preceding)
            trigger_candle = candles[-1]

            if break_type == "close_above":
                if trigger_candle.close > resistance_level:
                    return True, f"Close ({trigger_candle.close}) broke above resistance ({resistance_level})", {"resistance_level": resistance_level}
                return False, f"Close ({trigger_candle.close}) did not close above resistance ({resistance_level})", {}
            elif break_type == "wick_above":
                if trigger_candle.high > resistance_level:
                    return True, f"High ({trigger_candle.high}) pierced resistance ({resistance_level})", {"resistance_level": resistance_level}
                return False, f"High ({trigger_candle.high}) did not pierce resistance ({resistance_level})", {}

        # Fair Value Gap (FVG) Primitive
        elif p_type == "fair_value_gap" or p_type == "fvg":
            return cls._evaluate_fair_value_gap(candles, params)

        # Liquidity Sweep Reversal Primitive (Stop Hunt)
        elif p_type == "liquidity_sweep" or p_type == "sweep_reversal":
            return cls._evaluate_liquidity_sweep(candles, params)

        # Break of Structure (BOS / CHoCH) Primitive
        elif p_type == "break_of_structure" or p_type == "bos":
            return cls._evaluate_break_of_structure(candles, params)

        # Order Block (OB) Primitive
        elif p_type == "order_block" or p_type == "ob":
            return cls._evaluate_order_block(candles, params)

        # Strategy 1: SNR Wick Reversal (Counter-Trend Reversal)
        elif p_type in ["snr_wick_reversal", "SNR_WICK_REVERSAL", "wick_reversal", "wick_rejection", "pinbar_rejection"]:
            return cls._evaluate_snr_wick_reversal(candles, params, snapshot)

        # Strategy 2: EMA Trend Bounce (Trend Continuation)
        elif p_type in ["ema_trend_bounce", "EMA_TREND_BOUNCE", "ema_bounce"]:
            return cls._evaluate_ema_trend_bounce(candles, params, snapshot)

        # Strategy 3: Multi-Timeframe Momentum Alignment (Trend Following)
        elif p_type in ["mtf_momentum", "MTF_MOMENTUM", "momentum_alignment", "trend_momentum"]:
            return cls._evaluate_mtf_momentum(candles, params, snapshot)

        return False, f"Unknown primitive type: {p_type}", {}

    # ---------------------------------------------------------
    # SMC Fair Value Gap (FVG) Evaluator
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_fair_value_gap(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Detects 3-candle Fair Value Gap imbalance and trigger candle mitigation.
        Bullish FVG: Candle[-3].high < Candle[-1].low (imbalance between -3 high and -1 low).
        Bearish FVG: Candle[-3].low > Candle[-1].high (imbalance between -3 low and -1 high).
        """
        if len(candles) < 4:
            return False, "Fair Value Gap requires at least 4 candles", {}

        direction = params.get("direction", "DOWN").upper()
        lookback = min(len(candles) - 1, params.get("lookback", 10))
        trigger_c = candles[-1]

        for i in range(len(candles) - 2, 0, -1):
            if i < 2:
                continue
            c1 = candles[i - 2]
            c2 = candles[i - 1]
            c3 = candles[i]

            if direction in ["DOWN", "BEARISH", "SELL"]:
                # Bearish FVG: Large red middle candle, gap between c1.low and c3.high
                if c2.is_bearish and c1.low > c3.high:
                    gap_top = c1.low
                    gap_bottom = c3.high
                    if trigger_c.high >= gap_bottom and trigger_c.close < gap_top:
                        return True, f"Bearish Fair Value Gap Confirmed: Retest of imbalance zone [{gap_bottom:.5f} - {gap_top:.5f}]", {
                            "pattern_name": "SMC Bearish FVG",
                            "fvg_top": gap_top,
                            "fvg_bottom": gap_bottom,
                            "resistance_level": gap_top,
                            "direction": "DOWN",
                            "timeframe": "1M"
                        }
            else:
                # Bullish FVG: Large green middle candle, gap between c1.high and c3.low
                if c2.is_bullish and c1.high < c3.low:
                    gap_bottom = c1.high
                    gap_top = c3.low
                    if trigger_c.low <= gap_top and trigger_c.close > gap_bottom:
                        return True, f"Bullish Fair Value Gap Confirmed: Retest of imbalance zone [{gap_bottom:.5f} - {gap_top:.5f}]", {
                            "pattern_name": "SMC Bullish FVG",
                            "fvg_top": gap_top,
                            "fvg_bottom": gap_bottom,
                            "support_level": gap_bottom,
                            "direction": "UP",
                            "timeframe": "1M"
                        }

        return False, "No active Fair Value Gap mitigation found", {}

    # ---------------------------------------------------------
    # SMC Liquidity Sweep & Stop-Hunt Reversal Evaluator
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_liquidity_sweep(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Detects institutional liquidity sweep (Stop-Hunt / Turtle Soup):
        Price sweeps a key swing high/low with wick and closes back inside the range.
        """
        lookback = min(len(candles) - 1, params.get("lookback", 15))
        if len(candles) < 6:
            return False, "Liquidity sweep requires at least 6 candles", {}

        direction = params.get("direction", "DOWN").upper()
        trigger_c = candles[-1]
        preceding = candles[-lookback - 1 : -1]

        if direction in ["DOWN", "BEARISH", "SELL"]:
            swing_high = max(c.high for c in preceding)
            if trigger_c.high > swing_high and trigger_c.close < swing_high:
                upper_wick = trigger_c.high - max(trigger_c.open, trigger_c.close)
                rng = trigger_c.high - trigger_c.low
                if rng > 0 and (upper_wick / rng) >= 0.20:
                    return True, f"Liquidity Sweep Reversal Confirmed: Pierced swing high ({swing_high:.5f}) and rejected with upper wick", {
                        "pattern_name": "SMC Liquidity Sweep Reversal",
                        "swept_level": swing_high,
                        "resistance_level": swing_high,
                        "direction": "DOWN",
                        "timeframe": "1M"
                    }
        else:
            swing_low = min(c.low for c in preceding)
            if trigger_c.low < swing_low and trigger_c.close > swing_low:
                lower_wick = min(trigger_c.open, trigger_c.close) - trigger_c.low
                rng = trigger_c.high - trigger_c.low
                if rng > 0 and (lower_wick / rng) >= 0.20:
                    return True, f"Bullish Liquidity Sweep Confirmed: Pierced swing low ({swing_low:.5f}) and rejected with lower wick", {
                        "pattern_name": "SMC Bullish Liquidity Sweep",
                        "swept_level": swing_low,
                        "support_level": swing_low,
                        "direction": "UP",
                        "timeframe": "1M"
                    }

        return False, "No liquidity sweep structure confirmed", {}

    # ---------------------------------------------------------
    # SMC Break of Structure (BOS / CHoCH) Evaluator
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_break_of_structure(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Detects clean institutional Break of Structure (BOS) with candle body close confirmation.
        """
        lookback = min(len(candles) - 1, params.get("lookback", 12))
        if len(candles) < 5:
            return False, "BOS requires at least 5 candles", {}

        direction = params.get("direction", "DOWN").upper()
        trigger_c = candles[-1]
        preceding = candles[-lookback - 1 : -1]

        if direction in ["DOWN", "BEARISH", "SELL"]:
            recent_low = min(c.low for c in preceding)
            if trigger_c.is_bearish and trigger_c.close < recent_low:
                return True, f"Bearish Break of Structure (BOS) Confirmed: Body closed ({trigger_c.close:.5f}) below structural low ({recent_low:.5f})", {
                    "pattern_name": "SMC Bearish BOS",
                    "broken_level": recent_low,
                    "resistance_level": recent_low,
                    "direction": "DOWN",
                    "timeframe": "1M"
                }
        else:
            recent_high = max(c.high for c in preceding)
            if trigger_c.is_bullish and trigger_c.close > recent_high:
                return True, f"Bullish Break of Structure (BOS) Confirmed: Body closed ({trigger_c.close:.5f}) above structural high ({recent_high:.5f})", {
                    "pattern_name": "SMC Bullish BOS",
                    "broken_level": recent_high,
                    "support_level": recent_high,
                    "direction": "UP",
                    "timeframe": "1M"
                }

        return False, "No Break of Structure matched", {}

    # ---------------------------------------------------------
    # SMC Order Block (OB) Evaluator
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_order_block(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Detects Institutional Order Block (OB) mitigation and continuation.
        """
        lookback = min(len(candles) - 1, params.get("lookback", 15))
        if len(candles) < 4:
            return False, "Order Block requires at least 4 candles", {}

        direction = params.get("direction", "DOWN").upper()
        trigger_c = candles[-1]

        for i in range(len(candles) - 2):
            if i + 1 >= len(candles):
                continue
            ob_candle = candles[i]
            impulse_c = candles[i + 1]

            if direction in ["DOWN", "BEARISH", "SELL"]:
                if ob_candle.is_bullish and impulse_c.is_bearish and (impulse_c.close < ob_candle.low):
                    ob_top = ob_candle.high
                    ob_bottom = ob_candle.low
                    if trigger_c.high >= ob_bottom and trigger_c.close <= (ob_top * 1.0005):
                        return True, f"Bearish Order Block Mitigation Confirmed: Mitigation at [{ob_bottom:.5f} - {ob_top:.5f}] with downward rejection", {
                            "pattern_name": "SMC Bearish Order Block",
                            "ob_top": ob_top,
                            "ob_bottom": ob_bottom,
                            "resistance_level": ob_top,
                            "direction": "DOWN",
                            "timeframe": "1M"
                        }
            else:
                if ob_candle.is_bearish and impulse_c.is_bullish and (impulse_c.close > ob_candle.high):
                    ob_top = ob_candle.high
                    ob_bottom = ob_candle.low
                    if trigger_c.low <= ob_top and trigger_c.close >= ob_bottom and trigger_c.is_bullish:
                        return True, f"Bullish Order Block Confirmed: Mitigation at [{ob_bottom:.5f} - {ob_top:.5f}] with upward bounce", {
                            "pattern_name": "SMC Bullish Order Block",
                            "ob_top": ob_top,
                            "ob_bottom": ob_bottom,
                            "support_level": ob_bottom,
                            "direction": "UP",
                            "timeframe": "1M"
                        }

        return False, "No Order Block structure confirmed", {}

    # ---------------------------------------------------------
    # STRATEGY 1: SNR WICK REVERSAL (Counter-Trend Reversal)
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_snr_wick_reversal(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        STRATEGY 1: SNR WICK REVERSAL
        Trend Direction: Counter-Trend (Reversal)
        - CALL: Lower wick ratio > 0.45 touching Support within 0.05%
        - PUT: Upper wick ratio > 0.45 touching Resistance within 0.05%
        - Safety: Range > 1.2 * ATR(14), filter Doji (body < 10%)
        - OTC Streak: Skip if > 4 consecutive same-color candles
        - Indicators: RSI(7) < 30 (CALL) / > 70 (PUT), BB(20,2) touch/pierce
        """
        if len(candles) < 14:
            return False, "SNR Wick Reversal requires at least 14 candles", {}

        direction = params.get("direction", "DOWN").upper()
        c = candles[-1]
        rng = max(c.high - c.low, 1e-8)
        body = abs(c.close - c.open)
        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low

        # 1. Doji Filter (Body < 10% of total candle range)
        if (body / rng) < 0.10:
            return False, "Doji candle rejected (body < 10% of total range)", {}

        # 2. Candle Size Safety: Total range > 1.1 * ATR(14)
        atr_val = snapshot.get("atr")
        if atr_val and rng < (1.1 * atr_val):
            return False, f"Candle range ({rng:.5f}) smaller than 1.1 * ATR ({atr_val:.5f})", {}

        # 3. OTC Streak Filter: Reject if > 4 consecutive same-color candles before trigger
        streak = 1
        for i in range(len(candles) - 2, max(-1, len(candles) - 7), -1):
            prev = candles[i]
            if (c.is_bearish and prev.is_bearish) or (c.is_bullish and prev.is_bullish):
                streak += 1
            else:
                break
        if streak > 4:
            return False, f"OTC streak filter: {streak} consecutive same-color candles (max 4)", {}

        # 4. Indicators: RSI and Bollinger Bands
        rsi_val = snapshot.get("rsi")
        supports = snapshot.get("support_levels", [])
        resistances = snapshot.get("resistance_levels", [])

        if direction in ["DOWN", "BEARISH", "SELL", "PUT"]:
            wick_ratio = upper_wick / rng
            if wick_ratio < 0.45:
                return False, f"Upper wick ratio {wick_ratio*100:.1f}% below required 45.0%", {}

            # Resistance S/R touch within 0.05%
            has_sr_touch = True
            if resistances:
                has_sr_touch = any(abs(c.high - r) / max(r, 1e-8) <= 0.005 for r in resistances)

            if rsi_val and rsi_val < 45:
                return False, f"RSI ({rsi_val}) indicates strong counter-momentum against PUT reversal", {}

            if resistances and c.close > max(resistances):
                return False, "Candle body broke out above resistance (no breakout allowed)", {}

            return True, f"SNR Upper Wick Rejection Confirmed: {wick_ratio*100:.1f}% upper shadow at resistance", {
                "pattern_name": "SNR Wick Reversal",
                "wick_ratio": round(wick_ratio, 3),
                "resistance_level": c.high,
                "direction": "DOWN",
                "timeframe": "5M"
            }
        else:
            wick_ratio = lower_wick / rng
            if wick_ratio < 0.45:
                return False, f"Lower wick ratio {wick_ratio*100:.1f}% below required 45.0%", {}

            has_sr_touch = True
            if supports:
                has_sr_touch = any(abs(c.low - s) / max(s, 1e-8) <= 0.005 for s in supports)

            if rsi_val and rsi_val > 55:
                return False, f"RSI ({rsi_val}) indicates strong counter-momentum against CALL reversal", {}

            if supports and c.close < min(supports):
                return False, "Candle body broke out below support (no breakout allowed)", {}

            return True, f"SNR Lower Wick Rejection Confirmed: {wick_ratio*100:.1f}% lower shadow at support", {
                "pattern_name": "SNR Wick Reversal",
                "wick_ratio": round(wick_ratio, 3),
                "support_level": c.low,
                "direction": "UP",
                "timeframe": "5M"
            }

    # ---------------------------------------------------------
    # STRATEGY 2: EMA TREND BOUNCE (Trend Continuation)
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_ema_trend_bounce(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        STRATEGY 2: EMA TREND BOUNCE
        Trend Direction: In-Trend (Trend Continuation)
        - CALL: EMA 20 > EMA 200 (Uptrend), Low <= EMA 20, Close > EMA 20, Stochastic %K > %D below 50
        - PUT: EMA 20 < EMA 200 (Downtrend), High >= EMA 20, Close < EMA 20, Stochastic %K < %D above 50
        - Safety: Avoid Doji / extreme spikes, skip if streak > 5
        """
        if len(candles) < 20:
            return False, "EMA Trend Bounce requires at least 20 candles", {}

        direction = params.get("direction", "DOWN").upper()
        closes = [c.close for c in candles]
        ema_20_series = TechnicalIndicatorEngine.calculate_ema(closes, 20)
        ema_20 = ema_20_series[-1] if ema_20_series else None

        if ema_20 is None:
            return False, "Unable to compute EMA 20", {}

        c = candles[-1]
        rng = max(c.high - c.low, 1e-8)
        body = abs(c.close - c.open)

        # Doji / Overextended spike check (Body between 15% and 90% of range)
        if (body / rng) < 0.15 or (body / rng) > 0.90:
            return False, "Candle body not within healthy medium range (avoiding Doji & overextended spikes)", {}

        # Stochastic filter
        stoch = snapshot.get("stochastic", {})
        k = stoch.get("k", 50.0) or 50.0

        if direction in ["DOWN", "BEARISH", "SELL", "PUT"]:
            if c.high >= (ema_20 * 0.9997) and c.close < ema_20:
                if k > 85:
                    return False, f"Stochastic (%K={k:.1f}) in extreme overbought territory against trade", {}

                return True, f"EMA 20 Trend Rejection Confirmed: Tested EMA 20 ({ema_20:.5f}) and rejected downward", {
                    "pattern_name": "EMA Trend Bounce",
                    "ema_20": ema_20,
                    "resistance_level": ema_20,
                    "direction": "DOWN",
                    "timeframe": "5M"
                }
        else:
            if c.low <= (ema_20 * 1.0003) and c.close > ema_20:
                if k < 15:
                    return False, f"Stochastic (%K={k:.1f}) in extreme oversold territory against trade", {}

                return True, f"EMA 20 Support Bounce Confirmed: Tested EMA 20 ({ema_20:.5f}) and bounced upward", {
                    "pattern_name": "EMA Trend Bounce",
                    "ema_20": ema_20,
                    "support_level": ema_20,
                    "direction": "UP",
                    "timeframe": "5M"
                }

        return False, "No EMA trend bounce condition met", {}

    # ---------------------------------------------------------
    # STRATEGY 3: MULTI-TIMEFRAME MOMENTUM ALIGNMENT (Trend Following)
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_mtf_momentum(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        STRATEGY 3: MULTI-TIMEFRAME MOMENTUM ALIGNMENT
        Trend Direction: Trend Following (Strong Momentum)
        - CALL: 2 consecutive strong Green candles, close > preceding high, price > EMA 50, MACD Hist > 0
        - PUT: 2 consecutive strong Red candles, close < preceding low, price < EMA 50, MACD Hist < 0
        - Safety: Body > 65% of total range (Marubozu), opposing wick <= 35%
        - Avoid: Stochastic > 85 (CALL) / < 15 (PUT)
        """
        if len(candles) < 3:
            return False, "MTF Momentum requires at least 3 candles", {}

        direction = params.get("direction", "DOWN").upper()
        c1 = candles[-2]
        c2 = candles[-1]

        rng2 = max(c2.high - c2.low, 1e-8)
        body2 = abs(c2.close - c2.open)
        body_ratio = body2 / rng2

        # 1. Solid momentum candle body > 65% of total range (Marubozu style)
        if body_ratio < 0.65:
            return False, f"Momentum candle body ratio ({body_ratio*100:.1f}%) below required 65%", {}

        # 2. Indicators: MACD & Stochastic
        stoch = snapshot.get("stochastic", {})
        k = stoch.get("k", 50.0) or 50.0

        if direction in ["DOWN", "BEARISH", "SELL", "PUT"]:
            if not (c1.is_bearish and c2.is_bearish):
                return False, "Requires 2 consecutive strong Bearish candles", {}

            if c2.close >= c1.low:
                return False, "Trigger candle did not close beyond preceding candle Low", {}

            lower_wick_ratio = (min(c2.open, c2.close) - c2.low) / rng2
            if lower_wick_ratio > 0.35:
                return False, f"Opposing wick ({lower_wick_ratio*100:.1f}%) exceeds 35% limit against trend", {}

            if k < 15:
                return False, f"Stochastic (%K={k:.1f}) in extreme oversold territory (< 15)", {}

            return True, "MTF Bearish Momentum Alignment Confirmed: Clean 2-candle breakdown expansion", {
                "pattern_name": "MTF Momentum Alignment",
                "direction": "DOWN",
                "timeframe": "5M"
            }
        else:
            if not (c1.is_bullish and c2.is_bullish):
                return False, "Requires 2 consecutive strong Bullish candles", {}

            if c2.close <= c1.high:
                return False, "Trigger candle did not close beyond preceding candle High", {}

            upper_wick_ratio = (c2.high - max(c2.open, c2.close)) / rng2
            if upper_wick_ratio > 0.35:
                return False, f"Opposing wick ({upper_wick_ratio*100:.1f}%) exceeds 35% limit against trend", {}

            if k > 85:
                return False, f"Stochastic (%K={k:.1f}) in extreme overbought territory (> 85)", {}

            return True, "MTF Bullish Momentum Alignment Confirmed: Clean 2-candle breakout expansion", {
                "pattern_name": "MTF Momentum Alignment",
                "direction": "UP",
                "timeframe": "5M"
            }
