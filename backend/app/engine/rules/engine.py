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
        if len(candles) < 5:
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

        last_candle = candles[-1]
        direction = pattern_config.get("direction", "DOWN").upper()

        return {
            "matched": True,
            "direction": direction,
            "reason": "All deterministic pattern conditions successfully satisfied",
            "matched_at_candle_index": len(candles) - 1,
            "reference_price": last_candle.close,
            "support_level": context.get("support_level"),
            "resistance_level": context.get("resistance_level"),
            "technical_snapshot": snapshot,
            "rule_evaluation_log": log
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
            for idx, child in enumerate(conditions):
                pass_cond, reason, child_ctx = cls._evaluate_rule_node(child, candles, snapshot)
                context.update(child_ctx)
                if not pass_cond:
                    return False, f"AND branch {idx+1} failed: {reason}", context
            return True, "All AND conditions passed", context

        elif operator == "OR":
            for idx, child in enumerate(conditions):
                pass_cond, reason, child_ctx = cls._evaluate_rule_node(child, candles, snapshot)
                if pass_cond:
                    context.update(child_ctx)
                    return True, f"OR branch {idx+1} passed: {reason}", context
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

        return False, f"Unknown primitive type: {p_type}", {}

    # ---------------------------------------------------------
    # Pattern Type 14 Deterministic Evaluator
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_pattern_type_14(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Pattern Type 14 Specification:
        1. Context / Starting Bearish candle.
        2. First 2 Bullish candles (establishing a support base).
        3. Support level is created at the swing low of this base.
        4. Subsequent Bearish candle(s) develop.
        5. Support level broken with confirmation (close below support or wick below as configured).
        6. Confirms DOWN research signal.
        """
        bullish_count_req = params.get("bullish_count", 2)  # Default 2 bullish candles
        confirmation_type = params.get("confirmation", "close_below")  # close_below | wick_below
        support_source = params.get("support_source", "swing_low")  # swing_low | body_low

        # Need at least: 1 start bear + N bullish + 1 pullback bear + 1 breakout bear = (3 + N) candles
        min_required = 3 + bullish_count_req
        if len(candles) < min_required:
            return False, f"Pattern 14 requires at least {min_required} candles, got {len(candles)}", {}

        # Trigger candle is the last candle
        trigger_candle = candles[-1]
        if not trigger_candle.is_bearish:
            return False, f"Trigger candle must be bearish for DOWN signal, got close={trigger_candle.close} open={trigger_candle.open}", {}

        # Pullback candle (the candle right before trigger candle, or sequence of bearish candles)
        pullback_candle = candles[-2]
        if not pullback_candle.is_bearish:
            return False, f"Preceding candle must be bearish pullback, got close={pullback_candle.close} open={pullback_candle.open}", {}

        # The 2 bullish candles
        bullish_candles = candles[-(2 + bullish_count_req) : -2]
        if len(bullish_candles) != bullish_count_req:
            return False, f"Could not extract {bullish_count_req} bullish base candles", {}

        for i, c in enumerate(bullish_candles):
            if not c.is_bullish:
                return False, f"Base candle {i+1} of {bullish_count_req} is not bullish", {}

        # The initial bearish candle before the bullish base
        start_candle = candles[-(3 + bullish_count_req)]
        if not start_candle.is_bearish:
            return False, f"Starting candle before base must be bearish, got {start_candle.close} vs {start_candle.open}", {}

        # Compute support level from starting candle and base candles
        base_group = [start_candle] + bullish_candles
        if support_source == "swing_low":
            support_level = min(c.low for c in base_group)
        else:  # body_low
            support_level = min(min(c.open, c.close) for c in base_group)

        # Evaluate support break confirmation
        if confirmation_type == "close_below":
            if trigger_candle.close < support_level:
                return True, f"Pattern Type 14 Confirmed: Close ({trigger_candle.close}) closed below support level ({support_level:.5f})", {
                    "support_level": support_level,
                    "pattern_name": "Pattern Type 14",
                    "bullish_base_count": bullish_count_req
                }
            return False, f"Breakout failed: Close ({trigger_candle.close}) did not close below support ({support_level:.5f})", {}
        elif confirmation_type == "wick_below":
            if trigger_candle.low < support_level:
                return True, f"Pattern Type 14 Confirmed: Wick pierced support level ({support_level:.5f})", {
                    "support_level": support_level,
                    "pattern_name": "Pattern Type 14"
                }
            return False, f"Breakout failed: Low ({trigger_candle.low}) did not reach below support ({support_level:.5f})", {}

        return False, "Invalid confirmation type", {}

    @classmethod
    def _evaluate_pattern_type_14_inverted(cls, candles: List[Candle], params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Inverted Pattern Type 14 for UP signals (Bullish Start -> 2 Bearish -> Resistance Level -> Bullish Breakout)"""
        bearish_count_req = params.get("bearish_count", 2)
        confirmation_type = params.get("confirmation", "close_above")
        resistance_source = params.get("resistance_source", "swing_high")

        min_required = 3 + bearish_count_req
        if len(candles) < min_required:
            return False, f"Inverted Pattern 14 requires at least {min_required} candles", {}

        trigger_candle = candles[-1]
        if not trigger_candle.is_bullish:
            return False, "Trigger candle must be bullish for UP signal", {}

        pullback_candle = candles[-2]
        if not pullback_candle.is_bullish:
            return False, "Preceding candle must be bullish rally", {}

        bearish_candles = candles[-(2 + bearish_count_req) : -2]
        if len(bearish_candles) != bearish_count_req:
            return False, "Could not extract bearish base candles", {}

        for i, c in enumerate(bearish_candles):
            if not c.is_bearish:
                return False, f"Base candle {i+1} is not bearish", {}

        start_candle = candles[-(3 + bearish_count_req)]
        if not start_candle.is_bullish:
            return False, "Starting candle must be bullish", {}

        base_group = [start_candle] + bearish_candles
        if resistance_source == "swing_high":
            resistance_level = max(c.high for c in base_group)
        else:
            resistance_level = max(max(c.open, c.close) for c in base_group)

        if confirmation_type == "close_above":
            if trigger_candle.close > resistance_level:
                return True, f"Inverted Pattern Type 14 Confirmed: Close ({trigger_candle.close}) closed above resistance ({resistance_level:.5f})", {
                    "resistance_level": resistance_level,
                    "pattern_name": "Inverted Pattern Type 14"
                }
            return False, f"Breakout failed: Close ({trigger_candle.close}) did not close above resistance ({resistance_level:.5f})", {}

        return False, "Confirmation condition failed", {}

    # ---------------------------------------------------------
    # Pattern Type 1 Deterministic Evaluator (SMC 10 Line Reversal)
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_pattern_type_1(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Pattern Type 1 Specification:
        "If market forms two green candles followed by one red candle with normal bodies
        below the SMC 10 Line, the entry is a sure shot for a red candle in the opposite direction."

        Rules:
        1. Preceding 3 candles:
           - Candle -3 (1st): Green / Bullish
           - Candle -2 (2nd): Green / Bullish
           - Candle -1 (3rd): Red / Bearish (Signal Crowd reversal trigger)
        2. Indicator Condition:
           - SMC 10 Line (10-period moving average of price).
           - All 3 candles' bodies/closes are UNDER the SMC 10 Line (close <= smc_10_line).
        3. Generates DOWN / PUT signal for 1-minute expiration.
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

        # Calculate SMC 10 Line
        closes = [c.close for c in candles]
        smc_10_line = sum(closes[-smc_period:]) / float(smc_period)

        # Confirm price is UNDER SMC 10 Line
        if c1.close > smc_10_line or c2.close > smc_10_line or c3.close > smc_10_line:
            return False, f"Candles are not below SMC 10 Line ({smc_10_line:.5f})", {}

        return True, f"Pattern Type 1 Confirmed: 2 Green + 1 Red reversal below SMC 10 Line ({smc_10_line:.5f})", {
            "pattern_name": "Pattern Type 1",
            "smc_10_line": smc_10_line,
            "resistance_level": smc_10_line,
            "direction": "DOWN",
            "expiry_duration_minutes": 1,
            "timeframe": "1M"
        }

    # ---------------------------------------------------------
    # Pattern Type 15 Deterministic Evaluator (V-Pattern Rejection)
    # ---------------------------------------------------------

    @classmethod
    def _evaluate_pattern_type_15(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Pattern Type 15 Specification (V-Pattern Rejection):
        "If market makes a movement in 'V' Pattern and breakout the horizontal line
        then a sure shot will take place in opposite direction."

        Rules:
        1. Requires at least 6-15 candles to form the V-shape.
        2. Identify left swing high / horizontal resistance level before the drop.
        3. Identify swing low bottom (vertex of the 'V').
        4. Right side rallies back up to test / pierce the horizontal line.
        5. Trigger candle shows upper wick rejection or closes as a reversal red candle.
        6. Confirms DOWN / PUT signal for 1-minute expiration.
        """
        lookback = params.get("lookback", 10)
        if len(candles) < lookback + 2:
            return False, f"Pattern Type 15 requires at least {lookback + 2} candles, got {len(candles)}", {}

        trigger_candle = candles[-1]
        preceding = candles[-(lookback + 2) : -1]

        # Trigger candle must exhibit rejection: bearish candle OR prominent upper shadow
        upper_wick = trigger_candle.high - max(trigger_candle.open, trigger_candle.close)
        body = abs(trigger_candle.close - trigger_candle.open)

        if not trigger_candle.is_bearish and upper_wick < (body * 0.4):
            return False, f"Trigger candle lacks upper wick rejection or bearish close (upper_wick={upper_wick:.5f}, body={body:.5f})", {}

        # Horizontal line from left half of preceding candles
        half = len(preceding) // 2
        left_window = preceding[:half]
        if not left_window:
            return False, "Insufficient left window for horizontal line", {}

        horizontal_line = max(c.high for c in left_window)
        swing_low = min(c.low for c in preceding)

        # Trigger candle must reach or pierce horizontal line
        if trigger_candle.high < horizontal_line * 0.9992:
            return False, f"Trigger candle high ({trigger_candle.high}) did not reach horizontal resistance ({horizontal_line:.5f})", {}

        return True, f"Pattern Type 15 Confirmed: V-Pattern rally rejected at horizontal line ({horizontal_line:.5f}) with upper wick", {
            "pattern_name": "Pattern Type 15",
            "horizontal_line": horizontal_line,
            "resistance_level": horizontal_line,
            "swing_low": swing_low,
            "direction": "DOWN",
            "expiry_duration_minutes": 1,
            "timeframe": "1M"
        }

    @classmethod
    def _evaluate_pattern_type_15_inverted(
        cls,
        candles: List[Candle],
        params: Dict[str, Any],
        snapshot: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Inverted Pattern Type 15 Specification (Inverted V / Mountain Pattern Support Bounce):
        "If market makes an inverted 'V' Pattern and tests the horizontal support line,
        a reversal take place in UP direction."
        """
        lookback = params.get("lookback", 10)
        if len(candles) < lookback + 2:
            return False, f"Inverted Pattern Type 15 requires at least {lookback + 2} candles, got {len(candles)}", {}

        trigger_candle = candles[-1]
        preceding = candles[-(lookback + 2) : -1]

        lower_wick = min(trigger_candle.open, trigger_candle.close) - trigger_candle.low
        body = abs(trigger_candle.close - trigger_candle.open)

        if not trigger_candle.is_bullish and lower_wick < (body * 0.4):
            return False, "Trigger candle lacks lower wick bounce or bullish close", {}

        half = len(preceding) // 2
        left_window = preceding[:half]
        if not left_window:
            return False, "Insufficient left window for horizontal line", {}

        horizontal_line = min(c.low for c in left_window)
        swing_high = max(c.high for c in preceding)

        if trigger_candle.low > horizontal_line * 1.0008:
            return False, f"Trigger candle low ({trigger_candle.low}) did not reach horizontal support ({horizontal_line:.5f})", {}

        return True, f"Inverted Pattern Type 15 Confirmed: Inverted V bounce at horizontal line ({horizontal_line:.5f}) with lower wick", {
            "pattern_name": "Inverted Pattern Type 15",
            "horizontal_line": horizontal_line,
            "support_level": horizontal_line,
            "swing_high": swing_high,
            "direction": "UP",
            "expiry_duration_minutes": 1,
            "timeframe": "1M"
        }
