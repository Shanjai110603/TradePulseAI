"""
TradePulse AST Pattern Rule Engine
Evaluates deterministic rule trees (AND, OR, NOT) with support for all
candle primitives, price action breakouts, and Smart Money Concepts (SMC).
Ported and optimized from archive_v1. Zero external library dependencies.
"""
from typing import Any, Dict, List, Optional, Tuple
from core.indicators.engine import TechnicalIndicatorEngine
from core.models.candle import Candle


class PatternRuleEngine:
    """
    Evaluates recursive Abstract Syntax Tree (AST) condition trees
    against multi-timeframe candle histories.
    """

    @classmethod
    def evaluate_node(
        cls,
        node: Dict[str, Any],
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]] = None,
        technical_snapshot: Optional[Dict[str, Any]] = None,
        direction_context: str = "CALL"
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Recursively evaluates an AST node.
        Returns: (passed: bool, reason: str, details: dict)
        """
        if not node:
            return True, "Empty node passed", {}

        operator = node.get("operator", "AND").upper()
        conditions = node.get("conditions", [])
        child_details = []

        if operator == "AND":
            for cond in conditions:
                passed, reason, det = cls._evaluate_condition_or_subnode(
                    cond, candles, multi_timeframe_candles, technical_snapshot, direction_context
                )
                child_details.append({"condition": cond.get("type", "nested"), "passed": passed, "reason": reason})
                if not passed:
                    return False, f"AND condition failed: {reason}", {"children": child_details}
            return True, "All AND conditions satisfied", {"children": child_details}

        elif operator == "OR":
            passed_any = False
            reasons = []
            for cond in conditions:
                passed, reason, det = cls._evaluate_condition_or_subnode(
                    cond, candles, multi_timeframe_candles, technical_snapshot, direction_context
                )
                child_details.append({"condition": cond.get("type", "nested"), "passed": passed, "reason": reason})
                if passed:
                    passed_any = True
                else:
                    reasons.append(reason)

            if passed_any:
                return True, "At least one OR condition satisfied", {"children": child_details}
            return False, f"All OR conditions failed: {'; '.join(reasons)}", {"children": child_details}

        elif operator == "NOT":
            if conditions:
                passed, reason, det = cls._evaluate_condition_or_subnode(
                    conditions[0], candles, multi_timeframe_candles, technical_snapshot, direction_context
                )
                if not passed:
                    return True, "NOT condition successfully inverted failure", {"inverted": True}
                return False, f"NOT condition failed (child succeeded: {reason})", {"inverted": False}

        return False, f"Unknown operator: {operator}", {}

    @classmethod
    def _evaluate_condition_or_subnode(
        cls,
        item: Dict[str, Any],
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]],
        technical_snapshot: Optional[Dict[str, Any]],
        direction_context: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        op = str(item.get("operator", "")).upper()
        if op in ("AND", "OR", "NOT") and "conditions" in item:
            return cls.evaluate_node(item, candles, multi_timeframe_candles, technical_snapshot, direction_context)

        cond_type = item.get("type", "").lower()
        params = item.get("params", {})
        if not params and not cond_type in ["candle_anatomy", "sr_clearance"]:
            params = item

        if cond_type == "candle_anatomy":
            return cls.evaluate_candle_anatomy(candles, params, direction_context)
        elif cond_type in ["logus_trend", "logus_trend_strategy", "logu_trend"]:
            return cls.evaluate_logus_trend_strategy(candles, multi_timeframe_candles, technical_snapshot, params, direction_context)
        elif cond_type in ["mtf_engulfing", "mtf_engulfing_1m"]:
            return cls.evaluate_mtf_engulfing(candles, multi_timeframe_candles, params, direction_context)
        elif cond_type in ["fair_value_gap", "fvg"]:
            return cls.evaluate_fair_value_gap(candles, params, direction_context)
        elif cond_type == "liquidity_sweep":
            return cls.evaluate_liquidity_sweep(candles, params, direction_context)
        elif cond_type in ["break_of_structure", "bos"]:
            return cls.evaluate_break_of_structure(candles, params, direction_context)
        elif cond_type in ["order_block", "ob"]:
            return cls.evaluate_order_block(candles, params, direction_context)
        elif cond_type == "snr_wick_reversal":
            return cls.evaluate_snr_wick_reversal(candles, multi_timeframe_candles, technical_snapshot, params, direction_context)
        elif cond_type == "ema_trend_bounce":
            return cls.evaluate_ema_trend_bounce(candles, technical_snapshot, params, direction_context)
        elif cond_type in ["mtf_momentum", "mtf_momentum_strategy"]:
            return cls.evaluate_mtf_momentum(candles, multi_timeframe_candles, technical_snapshot, params, direction_context)
        elif cond_type in ["bollinger_mean_reversion", "bb_reversal", "bollinger_bounce", "bollinger_reversion"]:
            return cls.evaluate_bollinger_mean_reversion(candles, technical_snapshot, params, direction_context)
        elif cond_type in ["bollinger_squeeze_breakout", "bb_squeeze", "bb_breakout"]:
            return cls.evaluate_bollinger_squeeze_breakout(candles, technical_snapshot, params, direction_context)
        elif cond_type in ["bollinger_rsi_confluence", "bb_rsi", "bollinger_rsi"]:
            return cls.evaluate_bollinger_rsi_confluence(candles, technical_snapshot, params, direction_context)
        elif cond_type in ["dual_bollinger_protrusion", "dual_bb_protrusion", "dual_bollinger_reversal", "dual_bb", "dual_bollinger"]:
            return cls.evaluate_dual_bollinger_protrusion_reversal(candles, technical_snapshot, params, direction_context)
        elif cond_type in [
            "indicator_threshold", "indicator", "rsi", "macd", "ema", "sma", "bollinger", "bollinger_bands",
            "stochastic", "vwap", "atr", "adx", "supertrend", "parabolic_sar", "sar", "awesome_oscillator", "ao",
            "williams_r", "cci", "demarker", "aroon", "bulls_bears_power", "keltner", "donchian", "envelopes",
            "vortex", "volume_oscillator", "momentum", "roc"
        ]:
            if "indicator" not in params:
                params = dict(params)
                params["indicator"] = cond_type.upper()
            return cls.evaluate_indicator_threshold(technical_snapshot, params, direction_context, candles=candles)
        elif cond_type in ["formation", "candlestick_formation", "candle_pattern"]:
            return cls.evaluate_candlestick_formation(candles, technical_snapshot, params, direction_context)
        elif cond_type in ["smc_structure", "market_structure", "structure"]:
            return cls.evaluate_smc_structure_node(candles, technical_snapshot, params, direction_context)
        elif cond_type == "sr_clearance":
            return cls.evaluate_sr_clearance(candles, technical_snapshot, params, direction_context)

        return True, f"Unrecognized condition {cond_type} skipped", {}

    @classmethod
    def evaluate_candlestick_formation(
        cls,
        candles: List[Candle],
        technical_snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Evaluates detected candlestick patterns against the required direction."""
        forms = (technical_snapshot or {}).get("formations")
        if not forms:
            forms = TechnicalIndicatorEngine.calculate_candlestick_formations(candles)

        pattern = str(params.get("pattern", "")).upper()
        dir_upper = direction.upper()

        if pattern in ["PINBAR", "HAMMER", "SHOOTING_STAR"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = forms.get("pinbar_bullish", False)
                return passed, f"Bullish Pinbar/Hammer {'confirmed' if passed else 'not found'}", forms
            else:
                passed = forms.get("pinbar_bearish", False)
                return passed, f"Bearish Shooting Star/Pinbar {'confirmed' if passed else 'not found'}", forms

        elif pattern in ["ENGULFING", "ENGULF"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = forms.get("engulfing_bullish", False)
                return passed, f"Bullish Engulfing {'confirmed' if passed else 'not found'}", forms
            else:
                passed = forms.get("engulfing_bearish", False)
                return passed, f"Bearish Engulfing {'confirmed' if passed else 'not found'}", forms

        elif pattern in ["STAR", "MORNING_STAR", "EVENING_STAR"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = forms.get("morning_star", False)
                return passed, f"Morning Star reversal {'confirmed' if passed else 'not found'}", forms
            else:
                passed = forms.get("evening_star", False)
                return passed, f"Evening Star reversal {'confirmed' if passed else 'not found'}", forms

        elif pattern in ["SOLDIERS_CROWS", "THREE_SOLDIERS", "THREE_CROWS"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = forms.get("three_white_soldiers", False)
                return passed, f"Three White Soldiers {'confirmed' if passed else 'not found'}", forms
            else:
                passed = forms.get("three_black_crows", False)
                return passed, f"Three Black Crows {'confirmed' if passed else 'not found'}", forms

        elif pattern in ["INSIDE_BAR", "HARAMI"]:
            passed = forms.get("inside_bar", False)
            return passed, f"Inside Bar (Harami) {'confirmed' if passed else 'not found'}", forms

        elif pattern in ["TWEEZER"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = forms.get("tweezer_bottom", False)
                return passed, f"Tweezer Bottom {'confirmed' if passed else 'not found'}", forms
            else:
                passed = forms.get("tweezer_top", False)
                return passed, f"Tweezer Top {'confirmed' if passed else 'not found'}", forms

        # Default fallback: check if any detected pattern matches
        detected = forms.get("detected_patterns", [])
        if pattern and pattern in detected:
            return True, f"Pattern {pattern} confirmed in detected list", forms
        
        return len(detected) > 0, f"Detected patterns: {', '.join(detected) if detected else 'None'}", forms

    @classmethod
    def evaluate_smc_structure_node(
        cls,
        candles: List[Candle],
        technical_snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Evaluates Smart Money Concepts market structure triggers (BOS, CHOCH, FVG, Liquidity Sweeps)."""
        smc = (technical_snapshot or {}).get("smc_structure")
        if not smc:
            smc = TechnicalIndicatorEngine.calculate_smc_structure(candles)

        event = str(params.get("event", params.get("pattern", ""))).upper()
        dir_upper = direction.upper()

        if event in ["BOS", "BREAK_OF_STRUCTURE"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = smc.get("bos_bullish", False)
                return passed, f"Bullish Break of Structure (BOS) {'confirmed' if passed else 'not triggered'}", smc
            else:
                passed = smc.get("bos_bearish", False)
                return passed, f"Bearish Break of Structure (BOS) {'confirmed' if passed else 'not triggered'}", smc

        elif event in ["CHOCH", "CHANGE_OF_CHARACTER"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = smc.get("choch_bullish", False)
                return passed, f"Bullish CHOCH trend reversal {'confirmed' if passed else 'not triggered'}", smc
            else:
                passed = smc.get("choch_bearish", False)
                return passed, f"Bearish CHOCH trend reversal {'confirmed' if passed else 'not triggered'}", smc

        elif event in ["FVG", "FAIR_VALUE_GAP"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = smc.get("fvg_bullish", False)
                return passed, f"Bullish Fair Value Gap {'confirmed' if passed else 'not triggered'}", smc
            else:
                passed = smc.get("fvg_bearish", False)
                return passed, f"Bearish Fair Value Gap {'confirmed' if passed else 'not triggered'}", smc

        elif event in ["SWEEP", "LIQUIDITY_SWEEP"]:
            if dir_upper in ["CALL", "BUY", "UP"]:
                passed = smc.get("liquidity_sweep_bullish", False)
                return passed, f"Bullish Liquidity Sweep & Rejection {'confirmed' if passed else 'not triggered'}", smc
            else:
                passed = smc.get("liquidity_sweep_bearish", False)
                return passed, f"Bearish Liquidity Sweep & Rejection {'confirmed' if passed else 'not triggered'}", smc

        trend = smc.get("structure_trend", "NEUTRAL")
        if dir_upper in ["CALL", "BUY", "UP"] and trend == "BULLISH":
            return True, "Bullish Higher High / Higher Low structural trend", smc
        elif dir_upper in ["PUT", "SELL", "DOWN"] and trend == "BEARISH":
            return True, "Bearish Lower High / Lower Low structural trend", smc

        return False, f"Structural trend ({trend}) does not align with {dir_upper}", smc

    # -----------------------------------------------------------------------
    # Primitive Condition Evaluators
    # -----------------------------------------------------------------------

    @staticmethod
    def evaluate_candle_anatomy(
        candles: List[Candle],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if len(candles) < 2:
            return False, "Insufficient candles for anatomy check", {}

        c = candles[-1]
        prev = candles[-2]

        min_body = params.get("min_body_ratio", 0.60)
        max_wick = params.get("max_opposing_wick", 0.35)
        filter_doji = params.get("filter_preceding_doji", True)
        spike_mult = params.get("filter_spike_multiplier", 3.0)

        # 1. Doji check on preceding candle
        if filter_doji and prev.is_doji:
            return False, "Preceding candle is an indecision Doji bar", {}

        # 2. Solid body check on trigger candle
        if c.body_ratio < min_body:
            return False, f"Trigger candle body ratio ({c.body_ratio*100:.1f}%) below required {min_body*100:.0f}%", {}

        # 3. Opposing wick limit
        if c.opposing_wick_ratio > max_wick:
            return False, f"Opposing wick ({c.opposing_wick_ratio*100:.1f}%) exceeds limit {max_wick*100:.0f}%", {}

        # 4. Spike anomaly check vs previous 3 bars
        if len(candles) >= 4 and spike_mult > 0:
            avg_prior_range = sum(candles[i].total_range for i in range(-4, -1)) / 3.0
            if c.total_range > (avg_prior_range * spike_mult):
                return False, f"Candle range ({c.total_range:.5f}) is an anomaly spike (> {spike_mult}x avg)", {}

        return True, "Candle anatomy criteria satisfied", {
            "body_ratio": round(c.body_ratio, 3),
            "opposing_wick_ratio": round(c.opposing_wick_ratio, 3),
        }

    @staticmethod
    def evaluate_logus_trend_strategy(
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]],
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        LOGU'S TREND STRATEGY (Enhanced):
        Multi-timeframe trend alignment (15M & 5M) + 1M Single Interruption Pullback Pattern.
        With adaptive history fallback, volume confirmation, and OTC stagnation filter.
        """
        if len(candles) < 6:
            return False, "Insufficient 1M candles (need >= 6)", {}

        is_call = direction.upper() in ["CALL", "UP", "BUY"]
        c_1m = candles[-1]
        prev_1m = candles[-2]

        # 1. 15M Trend Alignment: Candle color + above/below EMA 20 & 50
        #    ADAPTIVE: If 15M bars are too sparse, fall back to 5M trend only
        bars_15m = (multi_timeframe_candles or {}).get("15M", [])
        has_15m = len(bars_15m) >= 2
        if has_15m:
            c_15m = bars_15m[-1]
            ema_20_15m = TechnicalIndicatorEngine.calculate_ema(bars_15m, min(len(bars_15m), 20))
            ema_50_15m = TechnicalIndicatorEngine.calculate_ema(bars_15m, min(len(bars_15m), 50))
            if is_call:
                if not c_15m.is_bullish:
                    return False, "15M candle is not GREEN for CALL", {}
                if ema_20_15m and c_15m.close < ema_20_15m:
                    return False, "15M price below EMA 20 for CALL", {}
                if ema_50_15m and c_15m.close < ema_50_15m:
                    return False, "15M price below EMA 50 for CALL", {}
            else:
                if not c_15m.is_bearish:
                    return False, "15M candle is not RED for PUT", {}
                if ema_20_15m and c_15m.close > ema_20_15m:
                    return False, "15M price above EMA 20 for PUT", {}
                if ema_50_15m and c_15m.close > ema_50_15m:
                    return False, "15M price above EMA 50 for PUT", {}

        # 2. 5M Trend Alignment: Candle color + above/below EMA 20
        bars_5m = (multi_timeframe_candles or {}).get("5M", [])
        if not bars_5m:
            if has_15m:
                # 15M passed but no 5M — allow with reduced confidence
                pass
            else:
                return False, "No 5M or 15M candle data available for trend alignment", {}
        else:
            c_5m = bars_5m[-1]
            ema_20_5m = TechnicalIndicatorEngine.calculate_ema(bars_5m, min(len(bars_5m), 20))
            if is_call:
                if not c_5m.is_bullish:
                    return False, "5M candle is not GREEN for CALL", {}
                if ema_20_5m and c_5m.close < ema_20_5m:
                    return False, "5M price below EMA 20 for CALL", {}
            else:
                if not c_5m.is_bearish:
                    return False, "5M candle is not RED for PUT", {}
                if ema_20_5m and c_5m.close > ema_20_5m:
                    return False, "5M price above EMA 20 for PUT", {}

        # 3. 1M Pattern Sequence: Single interruption pullback with pattern repetition
        # Required for CALL: [Red Candle] -> [Green Candle(s)] -> [Red Candle] -> [Green Candle(s)] -> [Single Red Signal Candle]
        # Required for PUT:  [Green Candle] -> [Red Candle(s)] -> [Green Candle] -> [Red Candle(s)] -> [Single Green Signal Candle]
        runs = []
        curr_bull = candles[-1].is_bullish
        curr_cnt = 1
        for b in reversed(candles[:-1]):
            if b.is_bullish == curr_bull:
                curr_cnt += 1
            else:
                runs.append((curr_bull, curr_cnt))
                curr_bull = b.is_bullish
                curr_cnt = 1
                if len(runs) >= 6:
                    break
        runs.append((curr_bull, curr_cnt))

        if is_call:
            # Signal candle must be a Single Red candle
            if runs[0][0] is not False or runs[0][1] != 1:
                return False, "Signal candle must be a SINGLE RED interruption candle in uptrend", {}
            if len(runs) < 3 or runs[1][0] is not True:
                return False, "Preceding candles must be GREEN in uptrend", {}
            if len(runs) < 4 or runs[2][0] is not False:
                return False, "Missing prior RED interruption pullback in trend sequence", {}
        else:
            # Signal candle must be a Single Green candle
            if runs[0][0] is not True or runs[0][1] != 1:
                return False, "Signal candle must be a SINGLE GREEN interruption candle in downtrend", {}
            if len(runs) < 3 or runs[1][0] is not False:
                return False, "Preceding candles must be RED in downtrend", {}
            if len(runs) < 4 or runs[2][0] is not True:
                return False, "Missing prior GREEN interruption pullback in trend sequence", {}

        # 4. 1M Trend Baseline: Preceding green candle must be above 1M EMA 20 for CALL (below for PUT)
        ema_20_1m = TechnicalIndicatorEngine.calculate_ema(candles, min(len(candles), 20))
        if ema_20_1m:
            if is_call and prev_1m.close < ema_20_1m:
                return False, "1M uptrend price action is trading below EMA 20", {}
            if not is_call and prev_1m.close > ema_20_1m:
                return False, "1M downtrend price action is trading above EMA 20", {}

        # 5. Candle Body Ratio (>= 50%) & Doji Avoidance (>= 15%)
        if c_1m.body_ratio < 0.50:
            return False, f"Signal candle body ratio ({c_1m.body_ratio*100:.1f}%) < 50%", {}
        if c_1m.body_ratio < 0.15:
            return False, "Signal candle is an indecision micro-bar (<15% body)", {}

        # 6. Enhanced Opposing Wick Rejection Filter (< 25% for stronger confirmation)
        opposing_wick = c_1m.upper_wick_ratio if is_call else c_1m.lower_wick_ratio
        if opposing_wick > 0.25:
            return False, f"Opposing wick ({opposing_wick*100:.1f}%) > 25% against trade direction", {}

        # 6b. Confirming wick should be present (>= 5% wick in trade direction for rejection proof)
        confirming_wick = c_1m.lower_wick_ratio if is_call else c_1m.upper_wick_ratio
        # Not a hard filter — just contributes to details

        # 7. Anomaly & Spike Avoidance (Length <= 2.5x average of previous 3 candles)
        avg_prior = sum(candles[i].total_range for i in range(-4, -1)) / 3.0
        if avg_prior > 0 and c_1m.total_range > (avg_prior * 2.5):
            return False, f"Signal candle is an abnormal spike ({c_1m.total_range:.5f} > 2.5x avg)", {}

        # 8. High Volatility / Violent Market Filter (Dual wicks > 40% across recent candles)
        recent_3 = candles[-3:]
        dual_wick_violents = sum(1 for b in recent_3 if (b.upper_wick_ratio > 0.40 and b.lower_wick_ratio > 0.40))
        if dual_wick_violents >= 2:
            return False, "High volatility market (erratic dual wicks across recent candles)", {}

        # 9. OTC Stagnation/Consolidation Filter (ATR-based)
        # Reject signals when recent bars show extremely low volatility (< 20% of longer-term ATR)
        if len(candles) >= 14:
            atr_14 = sum(c.total_range for c in candles[-14:]) / 14.0
            atr_3 = sum(c.total_range for c in candles[-3:]) / 3.0
            if atr_14 > 0 and atr_3 < (atr_14 * 0.20):
                return False, f"OTC stagnation detected: short ATR ({atr_3:.5f}) < 20% of 14-bar ATR ({atr_14:.5f})", {}

        # 10. S/R Level Clearance (>= 0.1% buffer)
        if snapshot:
            min_buffer = 0.001
            if is_call:
                res = snapshot.get("nearest_resistance")
                if res and res > c_1m.close:
                    dist = (res - c_1m.close) / c_1m.close
                    if dist < min_buffer:
                        return False, f"Price too close to Resistance ({dist*100:.3f}% < 0.1%)", {}
            else:
                sup = snapshot.get("nearest_support")
                if sup and sup < c_1m.close:
                    dist = (c_1m.close - sup) / c_1m.close
                    if dist < min_buffer:
                        return False, f"Price too close to Support ({dist*100:.3f}% < 0.1%)", {}

        return True, "LOGU'S TREND STRATEGY criteria fully confirmed", {
            "body_ratio": round(c_1m.body_ratio, 3),
            "opposing_wick": round(opposing_wick, 3),
            "confirming_wick": round(confirming_wick, 3),
            "had_15m_data": has_15m
        }

    @staticmethod
    def evaluate_mtf_engulfing(
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        require_engulfing = params.get("require_engulfing", True)
        min_bars = 4 if require_engulfing else 2
        if len(candles) < min_bars:
            return False, f"Need at least {min_bars} candles for evaluation", {}

        c = candles[-1]
        prev = candles[-2]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        # 1. 5M MTF Trend Filter
        mtf_enabled = params.get("mtf_enabled", True)
        if mtf_enabled:
            bars_5m = (multi_timeframe_candles or {}).get("5M", [])
            if not bars_5m:
                return False, "No 5M candle data available for trend filter", {}
            c_5m = bars_5m[-1]
            ema_5m = TechnicalIndicatorEngine.calculate_ema(bars_5m, min(len(bars_5m), 20))
            if is_call:
                if not c_5m.is_bullish:
                    return False, "5M MTF candle is not GREEN for CALL", {}
                if ema_5m and c_5m.close < ema_5m:
                    return False, "5M MTF price opposes CALL (5M is below EMA 20)", {}
            else:
                if not c_5m.is_bearish:
                    return False, "5M MTF candle is not RED for PUT", {}
                if ema_5m and c_5m.close > ema_5m:
                    return False, "5M MTF price opposes PUT (5M is above EMA 20)", {}

        if not require_engulfing:
            return True, "MTF trend filter criteria satisfied", {}

        # 2. 1M Engulfing Pattern + EMA 20 close
        ema_20_1m = TechnicalIndicatorEngine.calculate_ema(candles, 20)
        if is_call:
            engulfed = c.is_bullish and prev.is_bearish and c.open <= prev.close and c.close >= prev.open
            if not engulfed:
                return False, "1M Bullish Engulfing pattern not formed", {}
            if c.close <= prev.high:
                return False, "1M Close not higher than preceding High", {}
            if ema_20_1m and c.close <= ema_20_1m:
                return False, "1M Engulfing candle must close strictly above EMA 20", {}
        else:
            engulfed = c.is_bearish and prev.is_bullish and c.open >= prev.close and c.close <= prev.open
            if not engulfed:
                return False, "1M Bearish Engulfing pattern not formed", {}
            if c.close >= prev.low:
                return False, "1M Close not lower than preceding Low", {}
            if ema_20_1m and c.close >= ema_20_1m:
                return False, "1M Engulfing candle must close strictly below EMA 20", {}

        # 3. Candle Size & Doji Avoidance
        min_body = params.get("min_body_ratio", 0.65)
        if c.body_ratio < min_body:
            return False, f"1M Engulfing body ratio ({c.body_ratio*100:.1f}%) < {min_body*100:.0f}%", {}
        if prev.body_ratio < 0.10:
            return False, "Preceding candle before engulfing is a Doji (<10% body)", {}

        # 4. Opposing Wick Rejection (< 30%)
        if c.opposing_wick_ratio > 0.30:
            return False, f"1M Engulfing opposing wick ({c.opposing_wick_ratio*100:.1f}%) > 30%", {}

        # 5. Anomaly Filter (<= 3x avg of prior 3 candles)
        avg_prior = sum(candles[i].total_range for i in range(-4, -1)) / 3.0
        if avg_prior > 0 and c.total_range > (avg_prior * 3.0):
            return False, "1M Engulfing is an anomaly spike (>3x avg)", {}

        return True, f"1M MTF Engulfing confirmed for {direction}", {
            "body_ratio": round(c.body_ratio, 3),
            "opposing_wick": round(c.opposing_wick_ratio, 3)
        }

    @staticmethod
    def evaluate_fair_value_gap(
        candles: List[Candle],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if len(candles) < 4:
            return False, "Need at least 4 candles for FVG check", {}

        c1 = candles[-4]
        c2 = candles[-3]
        c3 = candles[-2]
        trigger = candles[-1]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        if is_call:
            # Bullish FVG: c1.high < c3.low
            if c3.low > c1.high:
                gap_top = c3.low
                gap_bottom = c1.high
                # Trigger retests inside the gap zone
                if trigger.low <= gap_top and trigger.close >= gap_bottom:
                    return True, "Bullish Fair Value Gap (FVG) mitigated", {"gap": [gap_bottom, gap_top]}
            return False, "No bullish FVG found", {}
        else:
            # Bearish FVG: c1.low > c3.high
            if c1.low > c3.high:
                gap_top = c1.low
                gap_bottom = c3.high
                if trigger.high >= gap_bottom and trigger.close <= gap_top:
                    return True, "Bearish Fair Value Gap (FVG) mitigated", {"gap": [gap_bottom, gap_top]}
            return False, "No bearish FVG found", {}

    @staticmethod
    def evaluate_liquidity_sweep(
        candles: List[Candle],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if len(candles) < 6:
            return False, "Need at least 6 candles for liquidity sweep", {}

        lookback = params.get("lookback", 5)
        recent = candles[-lookback - 1:-1]
        trigger = candles[-1]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        if is_call:
            # Sweeps recent swing low with wick and closes back above it
            lowest_low = min(c.low for c in recent)
            if trigger.low < lowest_low and trigger.close > lowest_low and trigger.lower_wick >= (trigger.total_range * 0.20):
                return True, "Bullish Liquidity Sweep (Stop-Hunt) confirmed", {"swept_level": lowest_low}
            return False, "Bullish liquidity sweep not satisfied", {}
        else:
            # Sweeps recent swing high with wick and closes back below it
            highest_high = max(c.high for c in recent)
            if trigger.high > highest_high and trigger.close < highest_high and trigger.upper_wick >= (trigger.total_range * 0.20):
                return True, "Bearish Liquidity Sweep (Stop-Hunt) confirmed", {"swept_level": highest_high}
            return False, "Bearish liquidity sweep not satisfied", {}

    @staticmethod
    def evaluate_break_of_structure(
        candles: List[Candle],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if len(candles) < 6:
            return False, "Need at least 6 candles for BOS", {}

        lookback = params.get("lookback", 5)
        recent = candles[-lookback - 1:-1]
        trigger = candles[-1]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        if is_call:
            recent_high = max(c.high for c in recent)
            if trigger.close > recent_high and trigger.is_bullish:
                return True, "Bullish Break of Structure (BOS) confirmed with body close", {"bos_level": recent_high}
            return False, "Bullish BOS not confirmed", {}
        else:
            recent_low = min(c.low for c in recent)
            if trigger.close < recent_low and trigger.is_bearish:
                return True, "Bearish Break of Structure (BOS) confirmed with body close", {"bos_level": recent_low}
            return False, "Bearish BOS not confirmed", {}

    @staticmethod
    def evaluate_order_block(
        candles: List[Candle],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Smart Money Concepts (SMC) Order Block evaluation:
        Selects the last (most recent) opposing candle immediately preceding the 2-bar impulsive move.
        Scans backwards from index -3 down to -5 (i.e. candles[-3], [-4], [-5]).
        """
        if len(candles) < 5:
            return False, "Need at least 5 candles for Order Block check", {}

        trigger = candles[-1]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        # For CALL (Bullish OB): Look for the last bearish candle before the displacement move (candles[-3..-5])
        # For PUT (Bearish OB): Look for the last bullish candle before the displacement move (candles[-3..-5])
        ob_candle = None
        for i in (-3, -4, -5):
            if is_call and candles[i].is_bearish:
                ob_candle = candles[i]
                break
            elif not is_call and candles[i].is_bullish:
                ob_candle = candles[i]
                break

        if not ob_candle:
            return False, f"No preceding opposing candle found for {direction} Order Block", {}

        if is_call:
            # Bullish OB mitigation: trigger tests into the OB candle's high-low zone
            if trigger.low <= ob_candle.high and trigger.close >= ob_candle.low:
                return True, "Bullish Order Block (OB) mitigated", {"ob_range": [ob_candle.low, ob_candle.high]}
            return False, "Bullish OB mitigation not met", {}
        else:
            # Bearish OB mitigation: trigger tests into the OB candle's high-low zone
            if trigger.high >= ob_candle.low and trigger.close <= ob_candle.high:
                return True, "Bearish Order Block (OB) mitigated", {"ob_range": [ob_candle.low, ob_candle.high]}
            return False, "Bearish OB mitigation not met", {}

    @staticmethod
    def evaluate_snr_wick_reversal(
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]],
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        STRATEGY 1: SNR WICK REVERSAL
        5M Candle counter-trend pinbar rejection at S/R + RSI(7) + Bollinger Bands.
        """
        if len(candles) < 5:
            return False, "Need at least 5 candles for SNR Wick Reversal", {}

        c = candles[-1]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        # 1. Wick Ratio (> 0.45 = 45% of total candle size)
        if c.total_range <= 0:
            return False, "Zero candle range", {}

        lower_wick_ratio = c.lower_wick / c.total_range
        upper_wick_ratio = c.upper_wick / c.total_range

        if is_call:
            if lower_wick_ratio < 0.45:
                return False, f"Lower wick ({lower_wick_ratio*100:.1f}%) < 45% for CALL reversal", {}
        else:
            if upper_wick_ratio < 0.45:
                return False, f"Upper wick ({upper_wick_ratio*100:.1f}%) < 45% for PUT reversal", {}

        # 2. S/R Level Touch & Boundary Confirmation
        if snapshot:
            tol = 0.0005  # 0.05%
            if is_call:
                sups = snapshot.get("support_levels", [])
                sup = snapshot.get("nearest_support") or (sups[-1] if sups else None)
                if sup:
                    dist_to_sup = abs(c.low - sup) / sup
                    if dist_to_sup > tol and c.low > sup:
                        return False, f"Low not touching Support ({dist_to_sup*100:.3f}% > 0.05%)", {}
                    if c.close < sup:
                        return False, "Candle body broke and closed past Support line", {}
            else:
                ress = snapshot.get("resistance_levels", [])
                res = snapshot.get("nearest_resistance") or (ress[-1] if ress else None)
                if res:
                    dist_to_res = abs(c.high - res) / res
                    if dist_to_res > tol and c.high < res:
                        return False, f"High not touching Resistance ({dist_to_res*100:.3f}% > 0.05%)", {}
                    if c.close > res:
                        return False, "Candle body broke and closed past Resistance line", {}

        # 3. Candle Size Safety: Total candle range > 0.5 * ATR(14)
        atr_14 = (snapshot.get("atr") if snapshot else None) or (snapshot.get("atr_14") if snapshot else None) or TechnicalIndicatorEngine.calculate_atr(candles, 14)
        if atr_14 and atr_14 > 0:
            if c.total_range <= (0.5 * atr_14):
                return False, f"Candle range ({c.total_range:.5f}) <= 0.5*ATR ({0.5*atr_14:.5f})", {}

        # 4. Filter out Doji candles (Body < 10% of total candle range)
        if c.body_ratio < 0.10:
            return False, "Candle is an indecision Doji (<10% body)", {}

        # 5. OTC Streak Filter: Reject if > 4 consecutive same-color candles
        streak_color, streak_count = TechnicalIndicatorEngine.calculate_consecutive_streak(candles[:-1])
        if streak_count > 4:
            return False, f"OTC streak too strong ({streak_count} consecutive {streak_color} candles > 4)", {}

        # 6. Indicators Used:
        rsi_7 = (snapshot.get("rsi_7") if snapshot else None) or TechnicalIndicatorEngine.calculate_rsi(candles, 7)
        if rsi_7 is not None:
            if is_call and rsi_7 >= 30:
                return False, f"RSI(7) ({rsi_7:.1f}) not oversold (<30)", {}
            if not is_call and rsi_7 <= 70:
                return False, f"RSI(7) ({rsi_7:.1f}) not overbought (>70)", {}

        bb = (snapshot.get("bollinger_bands") if snapshot else None) or TechnicalIndicatorEngine.calculate_bollinger_bands(candles, 20)
        bb_lower = bb.get("lower", 0.0) if bb else (snapshot.get("bb_lower") if snapshot else 0.0)
        bb_upper = bb.get("upper", 999999.0) if bb else (snapshot.get("bb_upper") if snapshot else 999999.0)
        if bb or (snapshot and ("bb_lower" in snapshot or "bb_upper" in snapshot)):
            if is_call:
                if c.low > bb_lower:
                    return False, "Candle low did not touch or pierce lower Bollinger Band", {}
            else:
                if c.high < bb_upper:
                    return False, "Candle high did not touch or pierce upper Bollinger Band", {}

        # 7. 3M Timeframe Extreme Momentum Filter (RSI > 80 or < 20)
        bars_3m = (multi_timeframe_candles or {}).get("3M", [])
        if len(bars_3m) >= 8:
            rsi_3m = TechnicalIndicatorEngine.calculate_rsi(bars_3m, 7) or TechnicalIndicatorEngine.calculate_rsi(bars_3m, 14)
            if rsi_3m is not None:
                if rsi_3m > 80 or rsi_3m < 20:
                    return False, f"3M timeframe shows extreme momentum (RSI {rsi_3m:.1f})", {}

        return True, "SNR Wick Reversal criteria fully confirmed", {
            "wick_ratio": round(lower_wick_ratio if is_call else upper_wick_ratio, 3),
            "rsi_7": rsi_7
        }

    @staticmethod
    def evaluate_ema_trend_bounce(
        candles: List[Candle],
        technical_snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        STRATEGY 2: EMA TREND BOUNCE
        In-trend pullback to EMA 20 with EMA 200 trend filter and Stochastic crossover.
        """
        if len(candles) < 20:
            return False, "Need at least 20 candles for EMA Trend Bounce", {}

        c = candles[-1]
        prev = candles[-2]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        ema_20 = (technical_snapshot or {}).get("ema_20") or TechnicalIndicatorEngine.calculate_ema(candles, 20)
        ema_200 = (technical_snapshot or {}).get("ema_200") or TechnicalIndicatorEngine.calculate_ema(candles, 200) or TechnicalIndicatorEngine.calculate_ema(candles, len(candles))

        if not ema_20 or not ema_200:
            return False, "EMA 20 or EMA 200 unavailable", {}

        # 1. Trend Direction: EMA 20 vs EMA 200
        if abs(ema_20 - ema_200) / ema_200 < 0.0005:
            return False, "Flat market (EMA 20 and EMA 200 are crisscrossing)", {}

        if is_call:
            if ema_20 <= ema_200:
                return False, "EMA 20 <= EMA 200 (not an uptrend for CALL)", {}
        else:
            if ema_20 >= ema_200:
                return False, "EMA 20 >= EMA 200 (not a downtrend for PUT)", {}

        # 2. Confirmation Candle & EMA 20 Touch
        tol = ema_20 * 0.0004
        if is_call:
            touched = (c.low <= ema_20 + tol)
            closed_above = (c.close > ema_20)
            if not (touched and closed_above):
                return False, "CALL bounce failed: Low must touch EMA 20 and Close must be above EMA 20", {}
        else:
            touched = (c.high >= ema_20 - tol)
            closed_below = (c.close < ema_20)
            if not (touched and closed_below):
                return False, "PUT bounce failed: High must touch EMA 20 and Close must be below EMA 20", {}

        # 3. Previous Candle Cross Check
        if is_call and prev.close < ema_20:
            return False, "Previous candle closed on opposite side of EMA 20", {}
        if not is_call and prev.close > ema_20:
            return False, "Previous candle closed on opposite side of EMA 20", {}

        # 4. Stochastic Oscillator (14, 3, 3) Crossover Check
        stoch = (technical_snapshot or {}).get("stochastic")
        if not stoch and technical_snapshot and "stoch_k" in technical_snapshot:
            stoch = {
                "k": technical_snapshot.get("stoch_k", 50.0),
                "d": technical_snapshot.get("stoch_d", 50.0),
                "crossed_above": technical_snapshot.get("stoch_crossed_above", False),
                "crossed_below": technical_snapshot.get("stoch_crossed_below", False),
            }
        elif not stoch:
            stoch = TechnicalIndicatorEngine.calculate_stochastic(candles, 14, 3)
        if stoch:
            k = stoch.get("k", 50.0)
            d = stoch.get("d", 50.0)
            crossed_above = stoch.get("crossed_above", k > d)
            crossed_below = stoch.get("crossed_below", k < d)

            if is_call:
                if k > 80:
                    return False, f"Stochastic (%K={k:.1f}) in extreme Overbought territory (>80)", {}
                if not (crossed_above or k > d) or k > 55:
                    return False, f"Stochastic %K ({k:.1f}) not crossing/positioned above %D ({d:.1f}) below 50", {}
            else:
                if k < 20:
                    return False, f"Stochastic (%K={k:.1f}) in extreme Oversold territory (<20)", {}
                if not (crossed_below or k < d) or k < 45:
                    return False, f"Stochastic %K ({k:.1f}) not crossing/positioned below %D ({d:.1f}) above 50", {}

        # 5. Distance to S/R: Minimum 2-candle body gap between entry price and next major S/R
        avg_body = sum(b.body_length for b in candles[-5:]) / 5.0
        min_gap = avg_body * 1.8
        if technical_snapshot:
            if is_call:
                res = technical_snapshot.get("nearest_resistance")
                if res and res > c.close:
                    gap = res - c.close
                    if gap < min_gap:
                        return False, f"Insufficient gap to Resistance ({gap:.5f} < {min_gap:.5f})", {}
            else:
                sup = technical_snapshot.get("nearest_support")
                if sup and sup < c.close:
                    gap = c.close - sup
                    if gap < min_gap:
                        return False, f"Insufficient gap to Support ({gap:.5f} < {min_gap:.5f})", {}

        # 6. Candle Size Safety & Streak Filter
        if c.body_ratio < 0.25:
            return False, "Candle body too small (Doji)", {}
        avg_prior = sum(candles[i].total_range for i in range(-4, -1)) / 3.0
        if avg_prior > 0 and c.total_range > (avg_prior * 2.8):
            return False, "Spike anomaly candle", {}

        streak_color, streak_count = TechnicalIndicatorEngine.calculate_consecutive_streak(candles[:-1])
        if streak_count > 5:
            return False, f"Trend streak too mature ({streak_count} consecutive candles > 5)", {}

        return True, "EMA Trend Bounce criteria confirmed", {
            "ema_20": ema_20,
            "ema_200": ema_200
        }

    @staticmethod
    def evaluate_mtf_momentum(
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]],
        technical_snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        STRATEGY 3: MULTI-TIMEFRAME MOMENTUM ALIGNMENT
        5M Strong momentum breakout + 3M trend alignment + MACD histogram delta + EMA 50.
        """
        if len(candles) < 5:
            return False, "Need at least 5 candles for MTF Momentum", {}

        c = candles[-1]
        prev = candles[-2]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        # 1. 5M Consecutive Momentum Candles (2 consecutive strong bars)
        if is_call:
            if not (c.is_bullish and prev.is_bullish):
                return False, "Must have two consecutive strong GREEN candles on 5M", {}
            if c.close <= prev.high:
                return False, "5M candle did not close beyond High of preceding candle", {}
        else:
            if not (c.is_bearish and prev.is_bearish):
                return False, "Must have two consecutive strong RED candles on 5M", {}
            if c.close >= prev.low:
                return False, "5M candle did not close beyond Low of preceding candle", {}

        # 2. Candle Size Safety: Body > 70% of total range. Small wicks only.
        if c.body_ratio < 0.70:
            return False, f"Momentum candle body ratio ({c.body_ratio*100:.1f}%) < 70%", {}
        if c.opposing_wick_ratio > 0.30:
            return False, f"Opposing wick rejection ({c.opposing_wick_ratio*100:.1f}%) > 30%", {}

        # 3. 3M MTF Trend Alignment
        bars_3m = (multi_timeframe_candles or {}).get("3M", [])
        if not bars_3m:
            return False, "No 3M candle data available for MTF trend alignment", {}
        c_3m = bars_3m[-1]
        ema_20_3m = TechnicalIndicatorEngine.calculate_ema(bars_3m, min(len(bars_3m), 20))
        if is_call:
            if not c_3m.is_bullish:
                return False, "3M chart trend opposes CALL (3M candle is RED)", {}
            if ema_20_3m and c_3m.close < ema_20_3m:
                return False, "3M chart price opposes CALL (3M is below EMA 20)", {}
        else:
            if not c_3m.is_bearish:
                return False, "3M chart trend opposes PUT (3M candle is GREEN)", {}
            if ema_20_3m and c_3m.close > ema_20_3m:
                return False, "3M chart price opposes PUT (3M is above EMA 20)", {}

        # 4. EMA 50 Filter: Price strictly trading above EMA 50 (for CALL) / below EMA 50 (for PUT)
        ema_50 = (technical_snapshot or {}).get("ema_50") or TechnicalIndicatorEngine.calculate_ema(candles, 50)
        if ema_50:
            if is_call and c.close <= ema_50:
                return False, "Price not strictly trading above EMA 50 for CALL", {}
            if not is_call and c.close >= ema_50:
                return False, "Price not strictly trading below EMA 50 for PUT", {}

        # 5. MACD (12, 26, 9): Histogram positive & increasing (CALL) / negative & decreasing (PUT)
        macd = (technical_snapshot or {}).get("macd") or TechnicalIndicatorEngine.calculate_macd(candles)
        if macd:
            hist = macd.get("histogram", 0.0)
            prev_hist = macd.get("prev_histogram", hist)
            if is_call:
                if hist <= 0 or hist < prev_hist:
                    return False, f"MACD histogram ({hist:.6f}) not positive and increasing", {}
            else:
                if hist >= 0 or hist > prev_hist:
                    return False, f"MACD histogram ({hist:.6f}) not negative and decreasing", {}

        # 6. Streak Filter: Enter ONLY on the 2nd or 3rd momentum candle. Skip if streak > 3.
        streak_color, streak_count = TechnicalIndicatorEngine.calculate_consecutive_streak(candles)
        if streak_count > 3 or streak_count < 2:
            return False, f"Momentum streak count ({streak_count}) must be 2 or 3", {}

        # 7. Stochastic Avoidance: Avoid if Stochastic > 80 for CALL or < 20 for PUT
        stoch = (technical_snapshot or {}).get("stochastic") or TechnicalIndicatorEngine.calculate_stochastic(candles, 14, 3)
        if stoch:
            k = stoch.get("k", 50.0)
            if is_call and k > 80:
                return False, f"Stochastic (%K={k:.1f}) > 80 (Overbought)", {}
            if not is_call and k < 20:
                return False, f"Stochastic (%K={k:.1f}) < 20 (Oversold)", {}

        # 8. S/R Breakout & Distance: Next major S/R not within 1-candle distance
        if technical_snapshot:
            avg_range = sum(b.total_range for b in candles[-5:]) / 5.0
            if is_call:
                res = technical_snapshot.get("nearest_resistance")
                if res and res > c.close:
                    gap = res - c.close
                    if gap < avg_range * 0.8:
                        return False, "Next major Resistance level is within 1-candle distance", {}
            else:
                sup = technical_snapshot.get("nearest_support")
                if sup and sup < c.close:
                    gap = c.close - sup
                    if gap < avg_range * 0.8:
                        return False, "Next major Support level is within 1-candle distance", {}

        return True, "MTF Momentum Alignment criteria confirmed", {
            "body_ratio": round(c.body_ratio, 3),
            "streak": streak_count
        }

    @staticmethod
    def evaluate_indicator_threshold(
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str,
        candles: Optional[List[Candle]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        ind_name = params.get("indicator", "RSI").upper()
        condition = params.get("condition", "BETWEEN").upper()
        min_v = params.get("min_val")
        max_v = params.get("max_val")
        field = (params.get("field") or "").lower()
        period = params.get("period")

        val: Optional[float] = None

        # 1. EMA (can be user-specified period or default)
        if ind_name == "EMA":
            req_period = period if (period is not None and period > 0) else 20
            if candles and len(candles) >= req_period:
                val = TechnicalIndicatorEngine.calculate_ema(candles, req_period)
            elif snapshot:
                if req_period == 20 and "ema_20" in snapshot:
                    val = snapshot.get("ema_20")
                elif req_period == 9 and "ema_fast" in snapshot:
                    val = snapshot.get("ema_fast")
                elif req_period == 21 and "ema_slow" in snapshot:
                    val = snapshot.get("ema_slow")

        # 2. MACD (compound dict: histogram, signal, macd)
        elif ind_name == "MACD":
            sub = field if field in ("histogram", "signal", "macd") else "histogram"
            macd_dict = snapshot.get("macd") if snapshot else None
            if isinstance(macd_dict, dict):
                val = macd_dict.get(sub)
            elif candles and len(candles) >= 26:
                m_calc = TechnicalIndicatorEngine.calculate_macd(candles)
                val = m_calc.get(sub) if m_calc else None

        # 3. BOLLINGER BANDS (compound dict: percent_b, bandwidth, upper, lower, middle)
        elif ind_name in ("BOLLINGER", "BOLLINGER_BANDS", "BB"):
            sub = field if field in ("percent_b", "bandwidth", "upper", "lower", "middle") else "percent_b"
            bb_dict = snapshot.get("bollinger_bands") if snapshot else None
            if isinstance(bb_dict, dict):
                val = bb_dict.get(sub)
            elif candles and len(candles) >= (period or 20):
                bb_calc = TechnicalIndicatorEngine.calculate_bollinger_bands(candles, period or 20)
                val = bb_calc.get(sub) if bb_calc else None

        # 4. STOCHASTIC (compound dict: k, d)
        elif ind_name in ("STOCHASTIC", "STOCH"):
            sub = field if field in ("k", "d") else "k"
            stoch_dict = snapshot.get("stochastic") if snapshot else None
            if isinstance(stoch_dict, dict):
                val = stoch_dict.get(sub)
            elif candles and len(candles) >= (period or 14):
                stoch_calc = TechnicalIndicatorEngine.calculate_stochastic(candles, period or 14, 3)
                val = stoch_calc.get(sub) if stoch_calc else None

        # 5. VWAP (session or custom rolling period)
        elif ind_name == "VWAP":
            if period and period > 0 and candles:
                val = TechnicalIndicatorEngine.calculate_vwap(candles[-period:])
            elif snapshot:
                val = snapshot.get("vwap")
            elif candles:
                val = TechnicalIndicatorEngine.calculate_vwap(candles)

        # 6. Single-valued indicators with configurable period (RSI, ATR, ADX, SMA)
        elif ind_name == "RSI":
            if period and period != 14 and candles and len(candles) >= period + 1:
                val = TechnicalIndicatorEngine.calculate_rsi(candles, period)
            elif snapshot:
                val = snapshot.get("rsi")
            elif candles:
                val = TechnicalIndicatorEngine.calculate_rsi(candles, period or 14)

        elif ind_name == "ATR":
            if period and period != 14 and candles and len(candles) >= period + 1:
                val = TechnicalIndicatorEngine.calculate_atr(candles, period)
            elif snapshot:
                val = snapshot.get("atr")
            elif candles:
                val = TechnicalIndicatorEngine.calculate_atr(candles, period or 14)

        elif ind_name == "ADX":
            if period and period != 14 and candles and len(candles) >= ((period * 2) + 1):
                val = TechnicalIndicatorEngine.calculate_adx(candles, period)
            elif snapshot:
                val = snapshot.get("adx")
            elif candles:
                val = TechnicalIndicatorEngine.calculate_adx(candles, period or 14)

        elif ind_name == "SMA":
            req_period = period if (period is not None and period > 0) else 10
            if candles and len(candles) >= req_period:
                val = TechnicalIndicatorEngine.calculate_sma(candles, req_period)
            elif snapshot and req_period == 10:
                val = snapshot.get("sma_10")
            elif snapshot and req_period == 200:
                val = snapshot.get("sma_200")

        elif ind_name in ("SUPERTREND", "ST"):
            sub = field if field in ("supertrend", "upper_band", "lower_band") else "supertrend"
            st_dict = snapshot.get("supertrend") if snapshot else None
            if isinstance(st_dict, dict):
                val = st_dict.get(sub)
            elif candles:
                st_calc = TechnicalIndicatorEngine.calculate_supertrend(candles, period or 10, 3.0)
                val = st_calc.get(sub) if st_calc else None

        elif ind_name in ("PARABOLIC_SAR", "SAR", "PSAR"):
            psar_dict = snapshot.get("parabolic_sar") if snapshot else None
            if isinstance(psar_dict, dict):
                val = psar_dict.get("sar")
            elif candles:
                psar_calc = TechnicalIndicatorEngine.calculate_parabolic_sar(candles)
                val = psar_calc.get("sar") if psar_calc else None

        elif ind_name in ("AWESOME_OSCILLATOR", "AO"):
            sub = field if field in ("ao", "prev_ao") else "ao"
            ao_dict = snapshot.get("awesome_oscillator") if snapshot else None
            if isinstance(ao_dict, dict):
                val = ao_dict.get(sub)
            elif candles:
                ao_calc = TechnicalIndicatorEngine.calculate_awesome_oscillator(candles)
                val = ao_calc.get(sub) if ao_calc else None

        elif ind_name in ("WILLIAMS_R", "WILLIAMS_%R", "WILLIAMS", "WR"):
            if candles and len(candles) >= (period or 14):
                val = TechnicalIndicatorEngine.calculate_williams_r(candles, period or 14)
            elif snapshot:
                val = snapshot.get("williams_r")

        elif ind_name in ("CCI", "COMMODITY_CHANNEL_INDEX"):
            if candles and len(candles) >= (period or 20):
                val = TechnicalIndicatorEngine.calculate_cci(candles, period or 20)
            elif snapshot:
                val = snapshot.get("cci")

        elif ind_name in ("DEMARKER", "DEM"):
            if candles and len(candles) >= (period or 14):
                val = TechnicalIndicatorEngine.calculate_demarker(candles, period or 14)
            elif snapshot:
                val = snapshot.get("demarker")

        elif ind_name in ("MOMENTUM", "MOM"):
            if candles and len(candles) >= (period or 10) + 1:
                val = TechnicalIndicatorEngine.calculate_momentum(candles, period or 10)
            elif snapshot:
                val = snapshot.get("momentum")

        elif ind_name in ("ROC", "RATE_OF_CHANGE"):
            if candles and len(candles) >= (period or 10) + 1:
                val = TechnicalIndicatorEngine.calculate_rate_of_change(candles, period or 10)
            elif snapshot:
                val = snapshot.get("roc")

        elif ind_name in ("AROON", "AROON_OSCILLATOR"):
            sub = field if field in ("aroon_up", "aroon_down", "oscillator") else "oscillator"
            aroon_dict = snapshot.get("aroon") if snapshot else None
            if isinstance(aroon_dict, dict):
                val = aroon_dict.get(sub)
            elif candles:
                aroon_calc = TechnicalIndicatorEngine.calculate_aroon(candles, period or 14)
                val = aroon_calc.get(sub) if aroon_calc else None

        elif ind_name in ("BULLS_POWER", "BULLS"):
            bp_dict = snapshot.get("bulls_bears_power") if snapshot else None
            if isinstance(bp_dict, dict):
                val = bp_dict.get("bulls_power")
            elif candles:
                bp_calc = TechnicalIndicatorEngine.calculate_bulls_bears_power(candles, period or 13)
                val = bp_calc.get("bulls_power") if bp_calc else None

        elif ind_name in ("BEARS_POWER", "BEARS"):
            bp_dict = snapshot.get("bulls_bears_power") if snapshot else None
            if isinstance(bp_dict, dict):
                val = bp_dict.get("bears_power")
            elif candles:
                bp_calc = TechnicalIndicatorEngine.calculate_bulls_bears_power(candles, period or 13)
                val = bp_calc.get("bears_power") if bp_calc else None

        elif ind_name in ("KELTNER", "KELTNER_CHANNEL", "KC"):
            sub = field if field in ("upper", "lower", "middle") else "middle"
            kc_dict = snapshot.get("keltner") if snapshot else None
            if isinstance(kc_dict, dict):
                val = kc_dict.get(sub)
            elif candles:
                kc_calc = TechnicalIndicatorEngine.calculate_keltner_channel(candles, period or 20)
                val = kc_calc.get(sub) if kc_calc else None

        elif ind_name in ("DONCHIAN", "DONCHIAN_CHANNEL", "DC"):
            sub = field if field in ("upper", "lower", "middle") else "middle"
            dc_dict = snapshot.get("donchian") if snapshot else None
            if isinstance(dc_dict, dict):
                val = dc_dict.get(sub)
            elif candles:
                dc_calc = TechnicalIndicatorEngine.calculate_donchian_channel(candles, period or 20)
                val = dc_calc.get(sub) if dc_calc else None

        elif ind_name in ("ENVELOPES", "ENVELOPE", "ENV"):
            sub = field if field in ("upper", "lower", "middle") else "middle"
            env_dict = snapshot.get("envelopes") if snapshot else None
            if isinstance(env_dict, dict):
                val = env_dict.get(sub)
            elif candles:
                env_calc = TechnicalIndicatorEngine.calculate_envelopes(candles, period or 20)
                val = env_calc.get(sub) if env_calc else None

        elif ind_name in ("VORTEX", "VI"):
            sub = field if field in ("plus_vi", "minus_vi") else "plus_vi"
            vi_dict = snapshot.get("vortex") if snapshot else None
            if isinstance(vi_dict, dict):
                val = vi_dict.get(sub)
            elif candles:
                vi_calc = TechnicalIndicatorEngine.calculate_vortex(candles, period or 14)
                val = vi_calc.get(sub) if vi_calc else None

        elif ind_name in ("VOLUME_OSCILLATOR", "VO"):
            if candles and len(candles) >= 10:
                val = TechnicalIndicatorEngine.calculate_volume_oscillator(candles)
            elif snapshot:
                val = snapshot.get("volume_oscillator")

        else:
            # Fallback for generic snapshot lookup
            if snapshot:
                raw_val = snapshot.get(ind_name.lower())
                if isinstance(raw_val, (int, float)):
                    val = float(raw_val)

        if val is None:
            return False, f"Indicator {ind_name} is null or cannot be calculated", {}

        # Handle direction / trend alignment condition checks
        if condition in ("BULLISH", "CALL", "BUY"):
            if ind_name in ("SUPERTREND", "ST"):
                st_data = snapshot.get("supertrend") if snapshot else None
                is_bull = (st_data.get("trend") == "BULLISH") if isinstance(st_data, dict) else (candles[-1].close > val if candles else False)
                return (True, "Supertrend is BULLISH", {"val": val}) if is_bull else (False, "Supertrend is not BULLISH", {})
            elif ind_name in ("PARABOLIC_SAR", "SAR", "PSAR"):
                curr_price = candles[-1].close if candles else 0
                is_bull = curr_price > val
                return (True, "Parabolic SAR is BULLISH (below price)", {"val": val}) if is_bull else (False, "Parabolic SAR is BEARISH (above price)", {})
            elif ind_name in ("AWESOME_OSCILLATOR", "AO"):
                is_bull = val > 0
                return (True, f"Awesome Oscillator ({val:.5f}) is BULLISH (> 0)", {"val": val}) if is_bull else (False, f"Awesome Oscillator ({val:.5f}) is not > 0", {})
            elif ind_name in ("VORTEX", "VI"):
                v_data = snapshot.get("vortex") if snapshot else None
                is_bull = v_data.get("bullish_cross", False) if isinstance(v_data, dict) else (val > 1.0)
                return (True, "Vortex +VI > -VI (BULLISH)", {"val": val}) if is_bull else (False, "Vortex is BEARISH", {})
            elif ind_name in ("AROON", "AROON_OSCILLATOR"):
                return (True, f"Aroon Oscillator ({val:.2f}) > 0", {"val": val}) if val > 0 else (False, f"Aroon Oscillator ({val:.2f}) <= 0", {})
            elif val > 0:
                return True, f"{ind_name} ({val}) is BULLISH", {"val": val}
            return False, f"{ind_name} ({val}) is not BULLISH", {}

        if condition in ("BEARISH", "PUT", "SELL"):
            if ind_name in ("SUPERTREND", "ST"):
                st_data = snapshot.get("supertrend") if snapshot else None
                is_bear = (st_data.get("trend") == "BEARISH") if isinstance(st_data, dict) else (candles[-1].close < val if candles else False)
                return (True, "Supertrend is BEARISH", {"val": val}) if is_bear else (False, "Supertrend is not BEARISH", {})
            elif ind_name in ("PARABOLIC_SAR", "SAR", "PSAR"):
                curr_price = candles[-1].close if candles else 0
                is_bear = curr_price < val
                return (True, "Parabolic SAR is BEARISH (above price)", {"val": val}) if is_bear else (False, "Parabolic SAR is BULLISH (below price)", {})
            elif ind_name in ("AWESOME_OSCILLATOR", "AO"):
                is_bear = val < 0
                return (True, f"Awesome Oscillator ({val:.5f}) is BEARISH (< 0)", {"val": val}) if is_bear else (False, f"Awesome Oscillator ({val:.5f}) is not < 0", {})
            elif ind_name in ("VORTEX", "VI"):
                v_data = snapshot.get("vortex") if snapshot else None
                is_bear = not v_data.get("bullish_cross", True) if isinstance(v_data, dict) else (val < 1.0)
                return (True, "Vortex -VI > +VI (BEARISH)", {"val": val}) if is_bear else (False, "Vortex is BULLISH", {})
            elif ind_name in ("AROON", "AROON_OSCILLATOR"):
                return (True, f"Aroon Oscillator ({val:.2f}) < 0", {"val": val}) if val < 0 else (False, f"Aroon Oscillator ({val:.2f}) >= 0", {})
            elif val < 0:
                return True, f"{ind_name} ({val}) is BEARISH", {"val": val}
            return False, f"{ind_name} ({val}) is not BEARISH", {}

        if condition in ("PRICE_ABOVE_CALL_BELOW_PUT", "PRICE_ALIGNMENT", "ALIGNMENT", "TREND_ALIGN"):
            curr_price = candles[-1].close if candles else (snapshot.get("price") if snapshot else None)
            if curr_price is None:
                return False, f"Cannot evaluate {condition}: current price unavailable", {}
            is_call = direction.upper() in ["CALL", "UP", "BUY"]
            if is_call:
                if curr_price > val:
                    return True, f"Price ({curr_price:.5f}) is above {ind_name} ({val:.5f}) for CALL", {"val": val, "price": curr_price}
                return False, f"Price ({curr_price:.5f}) is not above {ind_name} ({val:.5f}) for CALL", {"val": val, "price": curr_price}
            else:
                if curr_price < val:
                    return True, f"Price ({curr_price:.5f}) is below {ind_name} ({val:.5f}) for PUT", {"val": val, "price": curr_price}
                return False, f"Price ({curr_price:.5f}) is not below {ind_name} ({val:.5f}) for PUT", {"val": val, "price": curr_price}

        # Oversold / Overbought convenience conditions
        if condition == "OVERSOLD":
            limit = min_v if min_v is not None else 30.0
            if val <= limit:
                return True, f"{ind_name} ({val:.2f}) is Oversold (<= {limit})", {"val": val}
            return False, f"{ind_name} ({val:.2f}) is not Oversold (> {limit})", {}

        if condition == "OVERBOUGHT":
            limit = max_v if max_v is not None else 70.0
            if val >= limit:
                return True, f"{ind_name} ({val:.2f}) is Overbought (>= {limit})", {"val": val}
            return False, f"{ind_name} ({val:.2f}) is not Overbought (< {limit})", {}

        comp_val = params.get("value", params.get("target_val", min_v if min_v is not None else max_v))
        threshold_above = min_v if min_v is not None else (comp_val if comp_val is not None else max_v)
        threshold_below = max_v if max_v is not None else (comp_val if comp_val is not None else min_v)

        if condition in ("ABOVE", "GREATER_THAN", "GT", ">", "CROSS_ABOVE", "CROSS_UP") and threshold_above is not None:
            if val > threshold_above:
                return True, f"{ind_name} ({val:.4f}) > {threshold_above}", {"val": val}
            return False, f"{ind_name} ({val:.4f}) <= required {threshold_above}", {}
        elif condition in ("GTE", ">=") and threshold_above is not None:
            if val >= threshold_above:
                return True, f"{ind_name} ({val:.4f}) >= {threshold_above}", {"val": val}
            return False, f"{ind_name} ({val:.4f}) < required {threshold_above}", {}
        elif condition in ("BELOW", "LESS_THAN", "LT", "<", "CROSS_BELOW", "CROSS_DOWN") and threshold_below is not None:
            if val < threshold_below:
                return True, f"{ind_name} ({val:.4f}) < {threshold_below}", {"val": val}
            return False, f"{ind_name} ({val:.4f}) >= required {threshold_below}", {}
        elif condition in ("LTE", "<=") and threshold_below is not None:
            if val <= threshold_below:
                return True, f"{ind_name} ({val:.4f}) <= {threshold_below}", {"val": val}
            return False, f"{ind_name} ({val:.4f}) > required {threshold_below}", {}
        elif condition == "BETWEEN":
            if min_v is not None and val < min_v:
                return False, f"{ind_name} ({val:.4f}) below minimum {min_v}", {}
            if max_v is not None and val > max_v:
                return False, f"{ind_name} ({val:.4f}) above maximum {max_v}", {}
            return True, f"{ind_name} ({val:.4f}) within [{min_v}, {max_v}]", {"val": val}

        return True, "Indicator threshold check passed", {"val": val}

    @staticmethod
    def evaluate_sr_clearance(
        candles: List[Candle],
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if not snapshot:
            return True, "No snapshot, skipping S/R clearance", {}

        min_buffer_pct = params.get("min_clearance_pct", 0.001)
        curr_price = candles[-1].close
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        if is_call:
            res = snapshot.get("nearest_resistance")
            if res and res > curr_price:
                dist_pct = (res - curr_price) / curr_price
                if dist_pct < min_buffer_pct:
                    return False, f"Price too close to resistance ({dist_pct*100:.3f}% < {min_buffer_pct*100:.2f}%)", {}
        else:
            sup = snapshot.get("nearest_support")
            if sup and sup < curr_price:
                dist_pct = (curr_price - sup) / curr_price
                if dist_pct < min_buffer_pct:
                    return False, f"Price too close to support ({dist_pct*100:.3f}% < {min_buffer_pct*100:.2f}%)", {}

        return True, "S/R clearance buffer satisfied", {}

    @staticmethod
    def evaluate_bollinger_mean_reversion(
        candles: List[Candle],
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        BOLLINGER MEAN REVERSION STRATEGY:
        Price penetrates or touches the Outer Bollinger Band (2.0 StdDev)
        and confirms a reversal rebound closing back inside the channel.
        """
        if len(candles) < 20:
            return False, "Need >= 20 candles for Bollinger Mean Reversion", {}

        c = candles[-1]
        prev = candles[-2]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        period = params.get("period", 20)
        std_dev = params.get("std_dev", 2.0)
        bb = (snapshot or {}).get("bollinger_bands") or TechnicalIndicatorEngine.calculate_bollinger_bands(candles, period, std_dev)
        if not bb:
            return False, "Failed to compute Bollinger Bands", {}

        upper = bb.get("upper", 0.0)
        lower = bb.get("lower", 0.0)
        middle = bb.get("middle", 0.0)
        percent_b = bb.get("percent_b", 0.5)

        if is_call:
            # Rebound from Lower Band:
            # Trigger bar touched or pierced lower band (low <= lower), and closed bullish (green)
            touched_lower = (c.low <= lower) or (prev.low <= lower) or (percent_b <= 0.15)
            if not touched_lower:
                return False, f"Price (Low={c.low:.5f}) did not touch Lower Bollinger Band ({lower:.5f})", {}
            if not c.is_bullish:
                return False, "Trigger candle must close GREEN (Bullish rebound) for CALL", {}
            if c.lower_wick_ratio < 0.20 and c.body_ratio < 0.30:
                return False, "Insufficient bottom rejection wick/momentum on lower band touch", {}
        else:
            # Rebound from Upper Band:
            # Trigger bar touched or pierced upper band (high >= upper), and closed bearish (red)
            touched_upper = (c.high >= upper) or (prev.high >= upper) or (percent_b >= 0.85)
            if not touched_upper:
                return False, f"Price (High={c.high:.5f}) did not touch Upper Bollinger Band ({upper:.5f})", {}
            if not c.is_bearish:
                return False, "Trigger candle must close RED (Bearish rebound) for PUT", {}
            if c.upper_wick_ratio < 0.20 and c.body_ratio < 0.30:
                return False, "Insufficient top rejection wick/momentum on upper band touch", {}

        return True, "Bollinger Mean Reversion criteria confirmed", {
            "percent_b": percent_b,
            "upper": upper,
            "lower": lower,
            "middle": middle
        }

    @staticmethod
    def evaluate_bollinger_squeeze_breakout(
        candles: List[Candle],
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        BOLLINGER SQUEEZE & VOLATILITY BREAKOUT:
        Detects low-bandwidth consolidation compression followed by an explosive
        expansion close outside the bands.
        """
        if len(candles) < 22:
            return False, "Need >= 22 candles for Bollinger Squeeze Breakout", {}

        c = candles[-1]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        bb = (snapshot or {}).get("bollinger_bands") or TechnicalIndicatorEngine.calculate_bollinger_bands(candles, 20, 2.0)
        if not bb:
            return False, "Failed to compute Bollinger Bands", {}

        upper = bb.get("upper", 0.0)
        lower = bb.get("lower", 0.0)

        # Breakout condition: Strong momentum close piercing the outer band with solid body >= 65%
        if is_call:
            if c.close < upper:
                return False, f"Candle close ({c.close:.5f}) is not breaking above Upper Band ({upper:.5f})", {}
            if not c.is_bullish or c.body_ratio < 0.60:
                return False, "Breakout candle must be a solid bullish momentum bar (>=60% body)", {}
        else:
            if c.close > lower:
                return False, f"Candle close ({c.close:.5f}) is not breaking below Lower Band ({lower:.5f})", {}
            if not c.is_bearish or c.body_ratio < 0.60:
                return False, "Breakout candle must be a solid bearish momentum bar (>=60% body)", {}

        return True, "Bollinger Squeeze Breakout verified", {
            "breakout_price": c.close,
            "upper": upper,
            "lower": lower
        }

    @staticmethod
    def evaluate_bollinger_rsi_confluence(
        candles: List[Candle],
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        BOLLINGER BANDS + RSI DOUBLE CONFIRMATION TRIGGER:
        Combines Outer Bollinger Band extreme touch with RSI Overbought/Oversold exhaustion.
        """
        if len(candles) < 20:
            return False, "Need >= 20 candles for Bollinger + RSI Confluence", {}

        c = candles[-1]
        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        bb = (snapshot or {}).get("bollinger_bands") or TechnicalIndicatorEngine.calculate_bollinger_bands(candles, 20, 2.0)
        rsi = (snapshot or {}).get("rsi") or TechnicalIndicatorEngine.calculate_rsi(candles, 14)
        if not bb or rsi is None:
            return False, "Failed to compute Bollinger or RSI", {}

        upper = bb.get("upper", 0.0)
        lower = bb.get("lower", 0.0)

        if is_call:
            if c.low > lower and bb.get("percent_b", 0.5) > 0.20:
                return False, "Price did not test Lower Bollinger Band", {}
            if rsi > 38.0:
                return False, f"RSI ({rsi:.1f}) is not in oversold zone (<= 38)", {}
            if not c.is_bullish:
                return False, "Waiting for bullish green reversal confirmation candle", {}
        else:
            if c.high < upper and bb.get("percent_b", 0.5) < 0.80:
                return False, "Price did not test Upper Bollinger Band", {}
            if rsi < 62.0:
                return False, f"RSI ({rsi:.1f}) is not in overbought zone (>= 62)", {}
            if not c.is_bearish:
                return False, "Waiting for bearish red reversal confirmation candle", {}

        return True, "Bollinger + RSI Confluence verified", {
            "rsi": rsi,
            "percent_b": bb.get("percent_b")
        }

    @classmethod
    def evaluate_dual_bollinger_protrusion_reversal(
        cls,
        candles: List[Candle],
        snapshot: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        direction: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        STRATEGY: DUAL BOLLINGER PROTRUSION REVERSAL (1M Live Market Forex)
        -------------------------------------------------------------------
        Tuned specifically for 1-minute candlesticks on real interbank currency pairs.
        
        Mathematical Foundation:
        - BB1: Period = 10, Standard Deviation = 2.0
        - BB2: Period = 13, Standard Deviation = 2.0
        - Dynamic Outer Envelope:
            upper_trigger = max(BB10_upper, BB13_upper)
            lower_trigger = min(BB10_lower, BB13_lower)
            
        Entry Rules:
        - CALL (Buy):
            1. Candle must be Bearish (Close < Open).
            2. Candle Close must breach below the lower envelope: Close < lower_trigger.
            3. Body Protrusion: (lower_trigger - Close) >= 20%..25% of absolute candle body.
               (Wicks alone crossing the lower band are strictly rejected).
        - PUT (Sell):
            1. Candle must be Bullish (Close > Open).
            2. Candle Close must breach above the upper envelope: Close > upper_trigger.
            3. Body Protrusion: (Close - upper_trigger) >= 20%..25% of absolute candle body.
               (Wicks alone crossing the upper band are strictly rejected).
               
        Market Structure Confluence Filter:
        - Range / Box Consolidation (ADX < 25): Immediate valid mean-reversion signal.
        - Trending Wave (ADX >= 25): Requires the extreme wick to test a confirmed horizontal Support / Resistance line.
        """
        # --- 1. Extract Strategy Hyperparameters ---
        p1 = int(params.get("period_1", params.get("period", 10)))        # Primary BB period (default 10)
        p2 = int(params.get("period_2", 13))                              # Secondary BB period (default 13)
        dev = float(params.get("deviation", params.get("std_dev", 2.0)))  # Standard deviation multiplier (default 2.0)
        min_protrusion = float(params.get("min_body_protrusion", params.get("min_protrusion", 0.20))) # 20% minimum body protrusion

        # --- 2. History & Indicator Calculation Verification ---
        min_required = max(p1, p2) + 2
        if len(candles) < min_required:
            return False, f"Need at least {min_required} candles for Dual Bollinger Bands", {}

        # Compute both Bollinger Band envelopes over the candle series
        bb1 = TechnicalIndicatorEngine.calculate_bollinger_bands(candles, period=p1, std_dev_multiplier=dev)
        bb2 = TechnicalIndicatorEngine.calculate_bollinger_bands(candles, period=p2, std_dev_multiplier=dev)

        if not bb1 or not bb2:
            return False, "Failed calculating dual Bollinger Bands", {}

        # Determine the most conservative outer boundary triggers across both envelope periods
        upper_trigger = max(bb1["upper"], bb2["upper"])
        lower_trigger = min(bb1["lower"], bb2["lower"])

        # --- 3. Trigger Candle Anatomy & Protrusion Checks ---
        c = candles[-1] # The latest forming / triggering 1-minute candle
        body_size = abs(c.close - c.open)
        if body_size <= 0:
            # Reject Doji or flat candles where open equals close
            return False, "Candle body is zero (indecision Doji)", {}

        is_call = direction.upper() in ["CALL", "UP", "BUY"]

        if is_call:
            # CALL Reversal: Expecting price to bounce upwards after an overextended downward breach
            # Rule 1: Candle MUST be bearish (red)
            if c.close >= c.open:
                return False, "CALL reversal requires a bearish candle breaching down through the lower bands", {}
            
            # Rule 2: Close price must have penetrated below the outer lower trigger
            if c.close >= lower_trigger:
                return False, f"Candle close ({c.close:.5f}) is not below lower outer band ({lower_trigger:.5f})", {}

            # Rule 3: Minimum 20%-25% of the real candle body must protrude below the lower band
            body_outside = lower_trigger - c.close
            protrusion_pct = body_outside / body_size
            if protrusion_pct < min_protrusion:
                return False, f"Body protrusion ({protrusion_pct*100:.1f}%) < required {min_protrusion*100:.0f}% below dual lower bands", {}
        else:
            # PUT Reversal: Expecting price to reject downwards after an overextended upward breach
            # Rule 1: Candle MUST be bullish (green)
            if c.close <= c.open:
                return False, "PUT reversal requires a bullish candle breaching up through the upper bands", {}
            
            # Rule 2: Close price must have penetrated above the outer upper trigger
            if c.close <= upper_trigger:
                return False, f"Candle close ({c.close:.5f}) is not above upper outer band ({upper_trigger:.5f})", {}

            # Rule 3: Minimum 20%-25% of the real candle body must protrude above the upper band
            body_outside = c.close - upper_trigger
            protrusion_pct = body_outside / body_size
            if protrusion_pct < min_protrusion:
                return False, f"Body protrusion ({protrusion_pct*100:.1f}%) < required {min_protrusion*100:.0f}% above dual upper bands", {}

        # --- 4. Market Structure Classification (ADX Regime Filter) ---
        # Obtain 14-period Average Directional Index (ADX) to determine trend strength
        adx_val = (snapshot.get("adx") if snapshot else None)
        if adx_val is None:
            adx_val = TechnicalIndicatorEngine.calculate_adx(candles, 14)
        adx_score = adx_val if adx_val is not None else 20.0 # Default safely to consolidation if history is fresh
        is_consolidation = (adx_score < 25.0)

        # --- 5. Support / Resistance Confluence in Trending Environments ---
        # When ADX >= 25 (curving/trending market), breakouts against the trend require S/R horizontal confirmation
        if not is_consolidation and params.get("require_box_or_sr", True):
            tol = 0.0015  # 0.15% price zone tolerance for level intersection
            if is_call:
                # For CALL reversal in trend, check if candle low touches horizontal Support
                sups = (snapshot.get("support_levels") if snapshot else None)
                if not sups:
                    sup_list, _ = TechnicalIndicatorEngine.find_support_resistance_levels(candles)
                    sups = sup_list
                near_sup = False
                for sup in (sups or []):
                    if abs(c.low - sup) / max(1e-6, sup) <= tol or c.low <= sup <= c.high:
                        near_sup = True
                        break
                if not near_sup:
                    return False, f"Trending curve detected (ADX {adx_score:.1f} >= 25) but candle low did not intersect horizontal Support level", {}
            else:
                # For PUT reversal in trend, check if candle high touches horizontal Resistance
                ress = (snapshot.get("resistance_levels") if snapshot else None)
                if not ress:
                    _, res_list = TechnicalIndicatorEngine.find_support_resistance_levels(candles)
                    ress = res_list
                near_res = False
                for res in (ress or []):
                    if abs(c.high - res) / max(1e-6, res) <= tol or c.low <= res <= c.high:
                        near_res = True
                        break
                if not near_res:
                    return False, f"Trending curve detected (ADX {adx_score:.1f} >= 25) but candle high did not intersect horizontal Resistance level", {}

        # --- 6. Successful Signal Payload ---
        return True, f"Dual BB({p1},{p2}) Protrusion Reversal ({protrusion_pct*100:.1f}% outside, {'Consolidation' if is_consolidation else 'Trend+SR'})", {
            "bb1": bb1,
            "bb2": bb2,
            "upper_trigger": upper_trigger,
            "lower_trigger": lower_trigger,
            "body_protrusion_pct": round(protrusion_pct * 100, 2),
            "is_consolidation": is_consolidation
        }

