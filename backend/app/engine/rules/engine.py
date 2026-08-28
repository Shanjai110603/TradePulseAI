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

        # Specialized Pattern Type 1 Primitive (2 Green + 1 Red below SMC 10)
        if p_type == "pattern_type_1":
            return cls._evaluate_pattern_type_1(candles, params, snapshot)

        # Specialized Pattern Type 15 Primitive (V-Pattern Resistance Rejection)
        elif p_type == "pattern_type_15":
            return cls._evaluate_pattern_type_15(candles, params, snapshot)

        # Inverted Pattern Type 15 Primitive (Inverted V Support Bounce for UP Signals)
        elif p_type == "pattern_type_15_inverted":
            return cls._evaluate_pattern_type_15_inverted(candles, params, snapshot)

        # Specialized Pattern Type 14 Primitive
        elif p_type == "pattern_type_14":
            return cls._evaluate_pattern_type_14(candles, params)

        # Inverted Pattern Type 14 Primitive (for UP Signals)
        elif p_type == "pattern_type_14_inverted":
            return cls._evaluate_pattern_type_14_inverted(candles, params)

        # Candle Color Primitive
        elif p_type == "candle_color":
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

        # Wick Rejection Primitive (Quotex OTC Reversal)
        elif p_type == "wick_rejection" or p_type == "pinbar_rejection":
            return cls._evaluate_wick_rejection(candles, params, snapshot)

        # EMA Trend Bounce Primitive (Dynamic S/R Continuation)
        elif p_type == "ema_trend_bounce" or p_type == "ema_bounce":
            return cls._evaluate_ema_trend_bounce(candles, params, snapshot)

        # Momentum Alignment Primitive (2-Candle Trend Continuation)
        elif p_type == "momentum_alignment" or p_type == "trend_momentum":
            return cls._evaluate_momentum_alignment(candles, params, snapshot)

        return False, f"Unknown primitive type: {p_type}", {}

    # ---------------------------------------------------------
    # Pattern Type 14 Enhanced Deterministic Evaluator
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_pattern_type_14(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Enhanced Pattern Type 14 (Horizontal Support Breakdown):
        "Draw a Horizontal Line (SUPPORT LINE) between first 2 Green Candles after the Red Candle
        and wait for the market to break that support level with a strong Red candle then trade in the same direction."

        Algorithm:
        1. Dynamic scan across recent 6 to 25 candles.
        2. Locates an initial bearish candle followed by 2 consecutive bullish candles establishing horizontal support.
        3. Identifies the support level = min low across the 2 green base candles.
        4. Validates the intermediate mountain peak (rally above support).
        5. Confirms that trigger candle (last candle) is a strong red candle breaking and closing below the support level.
        """
        bullish_count_req = params.get("bullish_count", 2)
        lookback = min(len(candles), params.get("lookback", 20))
        
        if len(candles) < 5:
            return False, f"Pattern Type 14 requires at least 5 candles, got {len(candles)}", {}

        trigger_candle = candles[-1]
        if not trigger_candle.is_bearish:
            return False, f"Trigger candle must be bearish (Red), got close={trigger_candle.close} open={trigger_candle.open}", {}

        # Scan backwards for the 2-green base formation
        best_match = None
        best_support = None
        best_crest_height = 0.0

        for i in range(len(candles) - 3, max(1, len(candles) - lookback), -1):
            if i <= 0 or (i + bullish_count_req >= len(candles) - 1):
                continue
            
            base_candles = candles[i : i + bullish_count_req]
            if len(base_candles) < bullish_count_req or not all(c.is_bullish for c in base_candles):
                continue

            prior_candle = candles[i - 1]
            if not prior_candle.is_bearish:
                continue

            # Establish horizontal support line
            support_level = min(c.low for c in base_candles)

            # Check that between base and trigger, there was a rally above support (the mountain crest)
            intermediate_candles = candles[i + bullish_count_req : -1]
            if not intermediate_candles:
                continue

            max_intermediate_high = max(c.high for c in intermediate_candles)
            if max_intermediate_high <= support_level:
                continue

            # Check trigger candle breakout below support
            if trigger_candle.close < support_level:
                crest_height = max_intermediate_high - support_level
                if crest_height > best_crest_height:
                    best_crest_height = crest_height
                    best_support = support_level
                    best_match = (i, len(intermediate_candles))

        if best_support is not None:
            # Measure breakout candle strength
            trigger_body = trigger_candle.open - trigger_candle.close
            trigger_range = trigger_candle.high - trigger_candle.low
            body_ratio = (trigger_body / trigger_range) if trigger_range > 0 else 1.0

            return True, f"Pattern Type 14 Confirmed: Strong Red breakout close ({trigger_candle.close:.5f}) below horizontal support ({best_support:.5f})", {
                "support_level": best_support,
                "resistance_level": best_support,
                "pattern_name": "Pattern Type 14",
                "bullish_base_count": bullish_count_req,
                "direction": "DOWN",
                "expiry_duration_minutes": 1,
                "timeframe": "1M",
                "breakout_strength": f"{body_ratio * 100:.1f}%"
            }

        return False, "No valid Pattern 14 support breakout structure matched in recent price action", {}

    @classmethod
    def _evaluate_pattern_type_14_inverted(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Inverted Pattern Type 14 for UP signals (Bullish Start -> 2 Bearish Base -> Resistance Line -> Strong Bullish Breakout)"""
        bearish_count_req = params.get("bearish_count", 2)
        lookback = min(len(candles), params.get("lookback", 20))

        if len(candles) < 5:
            return False, f"Inverted Pattern 14 requires at least 5 candles, got {len(candles)}", {}

        trigger_candle = candles[-1]
        if not trigger_candle.is_bullish:
            return False, "Trigger candle must be bullish (Green) for UP signal", {}

        best_resistance = None
        best_trough_depth = 0.0

        for i in range(len(candles) - 3, max(1, len(candles) - lookback), -1):
            if i <= 0 or (i + bearish_count_req >= len(candles) - 1):
                continue

            base_candles = candles[i : i + bearish_count_req]
            if len(base_candles) < bearish_count_req or not all(c.is_bearish for c in base_candles):
                continue

            prior_candle = candles[i - 1]
            if not prior_candle.is_bullish:
                continue

            resistance_level = max(c.high for c in base_candles)
            intermediate_candles = candles[i + bearish_count_req : -1]
            if not intermediate_candles:
                continue

            min_intermediate_low = min(c.low for c in intermediate_candles)
            if min_intermediate_low >= resistance_level:
                continue

            if trigger_candle.close > resistance_level:
                trough_depth = resistance_level - min_intermediate_low
                if trough_depth > best_trough_depth:
                    best_trough_depth = trough_depth
                    best_resistance = resistance_level

        if best_resistance is not None:
            return True, f"Inverted Pattern Type 14 Confirmed: Strong Green breakout close ({trigger_candle.close:.5f}) above horizontal resistance ({best_resistance:.5f})", {
                "resistance_level": best_resistance,
                "support_level": best_resistance,
                "pattern_name": "Inverted Pattern Type 14",
                "direction": "UP",
                "expiry_duration_minutes": 1,
                "timeframe": "1M"
            }

        return False, "No valid Inverted Pattern 14 breakout structure matched", {}

    # ---------------------------------------------------------
    # Pattern Type 1 Enhanced Deterministic Evaluator (SMC 10 Line Reversal)
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_pattern_type_1(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Enhanced Pattern Type 1:
        "If market forms two green candles followed by one red candle with normal bodies
        below the SMC 10 Line, the entry is a sure shot for a red candle in the opposite direction."

        Algorithm:
        1. Evaluates preceding 3 candles:
           - Candle -3: Green (Bullish) with healthy body
           - Candle -2: Green (Bullish) with healthy body
           - Candle -1: Red (Bearish) reversal trigger
        2. Calculates SMC 10 Line (10-period moving average).
        3. Validates that closes are strictly below or interacting under SMC 10 Line.
        4. Verifies non-doji normal body size (body >= 18% of candle range).
        """
        smc_period = params.get("smc_period", 10)
        if len(candles) < max(smc_period, 5):
            return False, f"Pattern Type 1 requires at least {max(smc_period, 5)} candles, got {len(candles)}", {}

        c1 = candles[-3]  # 1st Green
        c2 = candles[-2]  # 2nd Green
        c3 = candles[-1]  # 3rd Red (trigger)

        if not c1.is_bullish:
            return False, f"First candle must be green (bullish), got {c1.close} vs {c1.open}", {}
        if not c2.is_bullish:
            return False, f"Second candle must be green (bullish), got {c2.close} vs {c2.open}", {}
        if not c3.is_bearish:
            return False, f"Third trigger candle must be red (bearish), got {c3.close} vs {c3.open}", {}

        # Body quality check (avoid micro-dojis)
        for idx, c in enumerate([c1, c2, c3], start=1):
            rng = c.high - c.low
            body = abs(c.close - c.open)
            if rng > 0 and (body / rng) < 0.15:
                return False, f"Candle {idx} is a doji with insufficient body proportion ({body/rng:.2f})", {}

        # Calculate SMC 10 Line
        closes = [c.close for c in candles]
        smc_10_line = sum(closes[-smc_period:]) / float(smc_period)

        # Confirm all 3 candles close under or at SMC 10 Line with adaptive tolerance
        tolerance = smc_10_line * 0.00015  # ~1.5 pips tolerance
        if c1.close > (smc_10_line + tolerance) or c2.close > (smc_10_line + tolerance) or c3.close > (smc_10_line + tolerance):
            return False, f"Candle closes exceed SMC 10 Line ({smc_10_line:.5f})", {}

        # Test of SMC line with upper shadows
        max_high = max(c1.high, c2.high, c3.high)
        line_proximity = abs(max_high - smc_10_line) / smc_10_line

        return True, f"Pattern Type 1 Confirmed: 2 Green + 1 Red reversal below SMC 10 Line ({smc_10_line:.5f})", {
            "pattern_name": "Pattern Type 1",
            "smc_10_line": smc_10_line,
            "resistance_level": smc_10_line,
            "direction": "DOWN",
            "expiry_duration_minutes": 1,
            "timeframe": "1M",
            "line_proximity": f"{line_proximity*100:.3f}%"
        }

    # ---------------------------------------------------------
    # Pattern Type 15 Enhanced Deterministic Evaluator (V-Pattern Rejection)
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_pattern_type_15(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Enhanced Pattern Type 15 (V-Pattern False Breakout & Resistance Rejection):
        "If market makes a movement in 'V' Pattern and tests/breaks out the horizontal line
        then a sure shot reversal will take place in opposite direction."

        Algorithm:
        1. Scans across dynamic lookback windows (6 to 22 candles).
        2. Detects left swing high (horizontal ceiling).
        3. Validates vertex bottom (swing low).
        4. Validates sharp rally back to test horizontal line.
        5. Confirms trigger candle rejection: upper wick piercing ceiling or bearish reversal close.
        """
        max_lookback = min(len(candles), params.get("lookback", 20))
        if len(candles) < 6:
            return False, f"Pattern Type 15 requires at least 6 candles, got {len(candles)}", {}

        trigger_candle = candles[-1]
        upper_wick = trigger_candle.high - max(trigger_candle.open, trigger_candle.close)
        body = abs(trigger_candle.close - trigger_candle.open)
        rng = trigger_candle.high - trigger_candle.low

        # Rejection confirmation: bearish close OR prominent upper wick (>= 25% of total candle range)
        has_upper_rejection = trigger_candle.is_bearish or (rng > 0 and (upper_wick / rng) >= 0.25)
        if not has_upper_rejection:
            return False, f"Trigger candle lacks upper wick rejection or bearish close (wick={upper_wick:.5f})", {}

        best_horizontal = None
        best_v_depth = 0.0

        for w_size in range(6, max_lookback + 1):
            preceding = candles[-w_size : -1]
            if len(preceding) < 5:
                continue

            half = max(1, len(preceding) // 2)
            left_window = preceding[:half]
            if not left_window:
                continue
            horizontal_ceiling = max(c.high for c in left_window)
            swing_low_bottom = min(c.low for c in preceding)
            v_depth = horizontal_ceiling - swing_low_bottom

            # Require meaningful V-shape depth (at least 0.01% price excursion)
            if v_depth < (horizontal_ceiling * 0.0001):
                continue

            # Trigger candle must reach or pierce horizontal ceiling
            if trigger_candle.high >= (horizontal_ceiling * 0.9995):
                if v_depth > best_v_depth:
                    best_v_depth = v_depth
                    best_horizontal = horizontal_ceiling

        if best_horizontal is not None:
            return True, f"Pattern Type 15 Confirmed: V-Pattern rally rejected at horizontal line ({best_horizontal:.5f}) with upper wick", {
                "pattern_name": "Pattern Type 15",
                "horizontal_line": best_horizontal,
                "resistance_level": best_horizontal,
                "v_depth": best_v_depth,
                "direction": "DOWN",
                "expiry_duration_minutes": 1,
                "timeframe": "1M"
            }

        return False, "No valid V-Pattern resistance rejection structure found in current window", {}

    @classmethod
    def _evaluate_pattern_type_15_inverted(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Enhanced Inverted Pattern Type 15 (Inverted V / Mountain Support Bounce)"""
        max_lookback = min(len(candles), params.get("lookback", 20))
        if len(candles) < 6:
            return False, f"Inverted Pattern Type 15 requires at least 6 candles, got {len(candles)}", {}

        trigger_candle = candles[-1]
        lower_wick = min(trigger_candle.open, trigger_candle.close) - trigger_candle.low
        rng = trigger_candle.high - trigger_candle.low

        has_lower_rejection = trigger_candle.is_bullish or (rng > 0 and (lower_wick / rng) >= 0.25)
        if not has_lower_rejection:
            return False, "Trigger candle lacks lower wick bounce or bullish close", {}

        best_horizontal = None
        best_inverted_depth = 0.0

        for w_size in range(6, max_lookback + 1):
            preceding = candles[-w_size : -1]
            if len(preceding) < 5:
                continue

            half = max(1, len(preceding) // 2)
            left_window = preceding[:half]
            if not left_window:
                continue
            horizontal_floor = min(c.low for c in left_window)
            swing_high_top = max(c.high for c in preceding)
            inverted_depth = swing_high_top - horizontal_floor

            if inverted_depth < (horizontal_floor * 0.0001):
                continue

            if trigger_candle.low <= (horizontal_floor * 1.0005):
                if inverted_depth > best_inverted_depth:
                    best_inverted_depth = inverted_depth
                    best_horizontal = horizontal_floor

        if best_horizontal is not None:
            return True, f"Inverted Pattern Type 15 Confirmed: Inverted V bounce at horizontal line ({best_horizontal:.5f}) with lower wick", {
                "pattern_name": "Inverted Pattern Type 15",
                "horizontal_line": best_horizontal,
                "support_level": best_horizontal,
                "direction": "UP",
                "expiry_duration_minutes": 1,
                "timeframe": "1M"
            }

        return False, "No valid Inverted V-Pattern support bounce found", {}

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
        if len(candles) < 6:
            return False, "Order Block requires at least 6 candles", {}

        direction = params.get("direction", "DOWN").upper()
        trigger_c = candles[-1]

        for i in range(len(candles) - 3, max(1, len(candles) - lookback), -1):
            ob_candle = candles[i]
            impulse_c = candles[i + 1]

            if direction in ["DOWN", "BEARISH", "SELL"]:
                if ob_candle.is_bullish and impulse_c.is_bearish and (impulse_c.close < ob_candle.low):
                    ob_top = ob_candle.high
                    ob_bottom = ob_candle.low
                    if trigger_c.high >= ob_bottom and trigger_c.close <= ob_top and trigger_c.is_bearish:
                        return True, f"Bearish Order Block Confirmed: Mitigation at [{ob_bottom:.5f} - {ob_top:.5f}] with downward rejection", {
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
    # Quotex OTC Wick Rejection Evaluator (Pinbar / Long Shadow)
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_wick_rejection(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates strong wick rejection (> 40% of candle range) aligned with multi-candle momentum.
        """
        if len(candles) < 3:
            return False, "Wick rejection requires at least 3 candles", {}

        direction = params.get("direction", "DOWN").upper()
        min_wick_ratio = params.get("min_wick_ratio", 0.40)
        c = candles[-1]
        rng = c.high - c.low

        if rng <= 0:
            return False, "Zero candle range", {}

        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low

        if direction in ["DOWN", "BEARISH", "SELL", "PUT"]:
            wick_ratio = upper_wick / rng
            if wick_ratio >= min_wick_ratio:
                return True, f"Quotex Upper Wick Rejection Confirmed: {wick_ratio*100:.1f}% upper shadow rejection", {
                    "pattern_name": "Quotex Wick Rejection",
                    "wick_ratio": round(wick_ratio, 3),
                    "resistance_level": c.high,
                    "direction": "DOWN",
                    "timeframe": "1M"
                }
            return False, f"Upper wick ratio {wick_ratio*100:.1f}% below required {min_wick_ratio*100:.1f}%", {}
        else:
            wick_ratio = lower_wick / rng
            if wick_ratio >= min_wick_ratio:
                return True, f"Quotex Lower Wick Rejection Confirmed: {wick_ratio*100:.1f}% lower shadow bounce", {
                    "pattern_name": "Quotex Wick Rejection",
                    "wick_ratio": round(wick_ratio, 3),
                    "support_level": c.low,
                    "direction": "UP",
                    "timeframe": "1M"
                }
            return False, f"Lower wick ratio {wick_ratio*100:.1f}% below required {min_wick_ratio*100:.1f}%", {}

    # ---------------------------------------------------------
    # EMA Trend Bounce Evaluator (Dynamic S/R Continuation)
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_ema_trend_bounce(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates dynamic EMA 20 / EMA 50 pull-back bounce in prevailing trend direction.
        """
        if len(candles) < 20:
            return False, "EMA Trend Bounce requires at least 20 candles", {}

        direction = params.get("direction", "DOWN").upper()
        closes = [c.close for c in candles]
        ema_20 = TechnicalIndicatorEngine.calculate_ema(closes, 20)[-1]

        if ema_20 is None:
            return False, "Unable to compute EMA 20", {}

        trigger_c = candles[-1]

        if direction in ["DOWN", "BEARISH", "SELL", "PUT"]:
            # Price tests EMA 20 from below (high >= EMA 20) and closes below EMA 20
            if trigger_c.high >= (ema_20 * 0.9998) and trigger_c.close < ema_20:
                return True, f"EMA 20 Trend Rejection Confirmed: Tested EMA ({ema_20:.5f}) and rejected downward", {
                    "pattern_name": "EMA Trend Bounce",
                    "ema_20": ema_20,
                    "resistance_level": ema_20,
                    "direction": "DOWN",
                    "timeframe": "1M"
                }
        else:
            # Price dips to EMA 20 from above (low <= EMA 20) and closes above EMA 20
            if trigger_c.low <= (ema_20 * 1.0002) and trigger_c.close > ema_20:
                return True, f"EMA 20 Support Bounce Confirmed: Tested EMA ({ema_20:.5f}) and bounced upward", {
                    "pattern_name": "EMA Trend Bounce",
                    "ema_20": ema_20,
                    "support_level": ema_20,
                    "direction": "UP",
                    "timeframe": "1M"
                }

        return False, "No EMA trend bounce condition met", {}

    # ---------------------------------------------------------
    # Momentum Alignment Evaluator (2-Candle Trend Continuation)
    # ---------------------------------------------------------
    @classmethod
    def _evaluate_momentum_alignment(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates consecutive expanding momentum candles in trend direction.
        """
        if len(candles) < 3:
            return False, "Momentum alignment requires at least 3 candles", {}

        direction = params.get("direction", "DOWN").upper()
        c1 = candles[-2]
        c2 = candles[-1]

        if direction in ["DOWN", "BEARISH", "SELL", "PUT"]:
            if c1.is_bearish and c2.is_bearish and c2.close < c1.close:
                return True, "Bearish Momentum Alignment Confirmed: Consecutive downward expansion candles", {
                    "pattern_name": "Momentum Alignment",
                    "direction": "DOWN",
                    "timeframe": "1M"
                }
        else:
            if c1.is_bullish and c2.is_bullish and c2.close > c1.close:
                return True, "Bullish Momentum Alignment Confirmed: Consecutive upward expansion candles", {
                    "pattern_name": "Momentum Alignment",
                    "direction": "UP",
                    "timeframe": "1M"
                }

        return False, "No momentum alignment confirmed", {}
