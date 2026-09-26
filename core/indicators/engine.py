"""
TradePulse Zero-Dependency Technical Indicator Engine
Pure Python mathematical implementation of 13 core indicators with no external
library dependencies (no TA-Lib, no pandas). Fast, portable, and mathematically verified.
"""
import math
from typing import Any, Dict, List, Optional, Tuple
from core.models.candle import Candle


class TechnicalIndicatorEngine:
    """
    Pure Python math engine for technical analysis indicators.
    All methods operate on chronological lists of Candle objects (oldest -> newest).
    """

    @staticmethod
    def calculate_sma(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Simple Moving Average (SMA)."""
        if len(candles) < period:
            return None
        closes = [c.close for c in candles[-period:]]
        return sum(closes) / period

    @staticmethod
    def calculate_ema(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Exponential Moving Average (EMA)."""
        if len(candles) < period:
            return None
        closes = [c.close for c in candles]
        k = 2.0 / (period + 1.0)
        # Seed with initial SMA
        ema = sum(closes[:period]) / period
        for price in closes[period:]:
            ema = (price * k) + (ema * (1.0 - k))
        return ema

    @staticmethod
    def calculate_rsi(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Relative Strength Index (RSI) using Wilder's smoothed RS."""
        if len(candles) < period + 1:
            return None

        closes = [c.close for c in candles]
        gains: List[float] = []
        losses: List[float] = []

        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff > 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0.0 else 50.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def calculate_macd(
        candles: List[Candle],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Optional[Dict[str, Any]]:
        """Moving Average Convergence Divergence (MACD) with delta tracking."""
        if len(candles) < slow_period + signal_period:
            return None

        closes = [c.close for c in candles]
        k_fast = 2.0 / (fast_period + 1.0)
        k_slow = 2.0 / (slow_period + 1.0)
        k_sig = 2.0 / (signal_period + 1.0)

        # Build MACD series
        ema_fast = sum(closes[:fast_period]) / fast_period
        for p in closes[fast_period:slow_period]:
            ema_fast = (p * k_fast) + (ema_fast * (1.0 - k_fast))

        ema_slow = sum(closes[:slow_period]) / slow_period
        macd_series: List[float] = []

        for p in closes[slow_period:]:
            ema_fast = (p * k_fast) + (ema_fast * (1.0 - k_fast))
            ema_slow = (p * k_slow) + (ema_slow * (1.0 - k_slow))
            macd_series.append(ema_fast - ema_slow)

        if len(macd_series) < signal_period:
            return None

        # Signal line: EMA of MACD series
        sig_series: List[float] = []
        sig_val = sum(macd_series[:signal_period]) / signal_period
        sig_series.append(sig_val)
        for val in macd_series[signal_period:]:
            sig_val = (val * k_sig) + (sig_val * (1.0 - k_sig))
            sig_series.append(sig_val)

        macd_val = macd_series[-1]
        signal_val = sig_series[-1]
        hist_val = macd_val - signal_val
        prev_hist = (macd_series[-2] - sig_series[-2]) if len(macd_series) >= 2 and len(sig_series) >= 2 else hist_val

        return {
            "macd": round(macd_val, 6),
            "signal": round(signal_val, 6),
            "histogram": round(hist_val, 6),
            "prev_histogram": round(prev_hist, 6),
            "hist_increasing": hist_val > prev_hist,
            "hist_decreasing": hist_val < prev_hist,
        }

    @staticmethod
    def calculate_bollinger_bands(
        candles: List[Candle],
        period: int = 20,
        std_dev_multiplier: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands (Upper, Middle/SMA, Lower, %B, Bandwidth).
        --------------------------------------------------------------------
        Mathematical Formulation:
          1. Middle Band = SMA(Close, period)
          2. Standard Deviation = sqrt( sum((Close_i - Middle)^2) / period )
          3. Upper Band = Middle + (std_dev_multiplier * Standard Deviation)
          4. Lower Band = Middle - (std_dev_multiplier * Standard Deviation)
          5. %B (Percent B) = (Current Close - Lower) / (Upper - Lower)
             - %B > 1.0 : Price is above the Upper Band (Overbought / Outlier)
             - %B < 0.0 : Price is below the Lower Band (Oversold / Outlier)
             - %B = 0.5 : Price is exactly at the Middle SMA
          6. Bandwidth = (Upper - Lower) / Middle
             - Measures relative volatility expansion vs squeeze consolidation.

        Args:
            candles: Chronological sequence of Candle objects.
            period: Lookback window for mean and variance (e.g., 10, 13, 20).
            std_dev_multiplier: Volatility expansion multiplier (typically 2.0).

        Returns:
            Dictionary containing upper, middle, lower, percent_b, and bandwidth,
            or None if candle count is less than required period.
        """
        if len(candles) < period:
            return None

        closes = [c.close for c in candles[-period:]]
        mean = sum(closes) / period
        variance = sum((x - mean) ** 2 for x in closes) / period
        std_dev = math.sqrt(variance)

        upper = mean + (std_dev_multiplier * std_dev)
        lower = mean - (std_dev_multiplier * std_dev)
        current = closes[-1]
        
        # Calculate %B oscillator normalized from 0.0 to 1.0 (can exceed range during breakouts)
        percent_b = (current - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

        return {
            "upper": round(upper, 5),
            "middle": round(mean, 5),
            "lower": round(lower, 5),
            "percent_b": round(percent_b, 4),
            "bandwidth": round((upper - lower) / mean, 5) if mean > 0 else 0.0,
        }

    @staticmethod
    def calculate_atr(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Average True Range (ATR) with Wilder's smoothing."""
        if len(candles) < period + 1:
            return None

        true_ranges: List[float] = []
        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]
            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close)
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return None

        atr = sum(true_ranges[:period]) / period
        for tr in true_ranges[period:]:
            atr = ((atr * (period - 1)) + tr) / period
        return round(atr, 6)

    @staticmethod
    def calculate_adx(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Average Directional Index (ADX)."""
        if len(candles) < (period * 2) + 1:
            return None

        tr_list: List[float] = []
        plus_dm: List[float] = []
        minus_dm: List[float] = []

        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]

            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close)
            )
            tr_list.append(tr)

            up_move = curr.high - prev.high
            down_move = prev.low - curr.low

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0.0)

            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0.0)

        # Smooth TR and DMs
        tr_smooth = sum(tr_list[:period])
        plus_dm_smooth = sum(plus_dm[:period])
        minus_dm_smooth = sum(minus_dm[:period])

        dx_list: List[float] = []
        for i in range(period, len(tr_list)):
            tr_smooth = tr_smooth - (tr_smooth / period) + tr_list[i]
            plus_dm_smooth = plus_dm_smooth - (plus_dm_smooth / period) + plus_dm[i]
            minus_dm_smooth = minus_dm_smooth - (minus_dm_smooth / period) + minus_dm[i]

            plus_di = (100.0 * plus_dm_smooth / tr_smooth) if tr_smooth > 0 else 0.0
            minus_di = (100.0 * minus_dm_smooth / tr_smooth) if tr_smooth > 0 else 0.0

            di_sum = plus_di + minus_di
            dx = (100.0 * abs(plus_di - minus_di) / di_sum) if di_sum > 0 else 0.0
            dx_list.append(dx)

        if len(dx_list) < period:
            return None

        adx = sum(dx_list[:period]) / period
        for dx in dx_list[period:]:
            adx = ((adx * (period - 1)) + dx) / period
        return round(adx, 2)

    @staticmethod
    def calculate_stochastic(
        candles: List[Candle],
        k_period: int = 14,
        d_period: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Stochastic Oscillator (%K, %D) with previous bar history for crossover checks."""
        if len(candles) < k_period + d_period:
            return None

        k_values: List[float] = []
        for i in range(k_period, len(candles) + 1):
            sub = candles[i - k_period:i]
            high_max = max(c.high for c in sub)
            low_min = min(c.low for c in sub)
            close = sub[-1].close
            rng = high_max - low_min
            k = ((close - low_min) / rng * 100.0) if rng > 0 else 50.0
            k_values.append(k)

        if len(k_values) < d_period:
            return None

        d_values = []
        for i in range(d_period, len(k_values) + 1):
            d_values.append(sum(k_values[i - d_period:i]) / d_period)

        k_curr = round(k_values[-1], 2)
        d_curr = round(d_values[-1], 2)
        k_prev = round(k_values[-2], 2) if len(k_values) >= 2 else k_curr
        d_prev = round(d_values[-2], 2) if len(d_values) >= 2 else d_curr

        # Crossover detection
        crossed_above = (k_prev <= d_prev) and (k_curr > d_curr)
        crossed_below = (k_prev >= d_prev) and (k_curr < d_curr)

        return {
            "k": k_curr,
            "d": d_curr,
            "prev_k": k_prev,
            "prev_d": d_prev,
            "crossed_above": crossed_above,
            "crossed_below": crossed_below,
        }

    @staticmethod
    def calculate_consecutive_streak(candles: List[Candle]) -> Tuple[str, int]:
        """
        Returns (color, count) of consecutive same-color candles leading to the end.
        e.g. ('GREEN', 3) or ('RED', 4).
        """
        if not candles:
            return ("NEUTRAL", 0)

        last = candles[-1]
        color = "GREEN" if last.is_bullish else ("RED" if last.is_bearish else "DOJI")
        if color == "DOJI":
            return ("DOJI", 1)

        streak = 0
        for c in reversed(candles):
            c_color = "GREEN" if c.is_bullish else ("RED" if c.is_bearish else "DOJI")
            if c_color == color:
                streak += 1
            else:
                break
        return (color, streak)

    @staticmethod
    def calculate_vwap(candles: List[Candle]) -> Optional[float]:
        """Volume Weighted Average Price (VWAP)."""
        if not candles:
            return None
        cum_vol_price = sum(((c.high + c.low + c.close) / 3.0) * c.volume for c in candles)
        cum_vol = sum(c.volume for c in candles)
        return round(cum_vol_price / cum_vol, 5) if cum_vol > 0 else candles[-1].close

    @staticmethod
    def find_support_resistance_levels(candles: List[Candle], lookback: int = 3) -> Tuple[List[float], List[float]]:
        """Detects swing lows (support) and swing highs (resistance)."""
        support: List[float] = []
        resistance: List[float] = []
        n = len(candles)

        if n < (lookback * 2) + 1:
            # Use historical prior candles (excluding trigger candle) to prevent self-collision
            priors = candles[:-1] if len(candles) > 1 else candles
            return [c.low for c in priors[-3:]], [c.high for c in priors[-3:]]

        for i in range(lookback, n - lookback):
            current = candles[i]
            is_swing_high = True
            is_swing_low = True

            for j in range(i - lookback, i + lookback + 1):
                if j == i:
                    continue
                if candles[j].high >= current.high:
                    is_swing_high = False
                if candles[j].low <= current.low:
                    is_swing_low = False

            if is_swing_high:
                resistance.append(current.high)
            if is_swing_low:
                support.append(current.low)

        return support[-5:], resistance[-5:]

    @staticmethod
    def is_market_flatlined(candles: List[Candle], lookback: int = 3, min_range_pct: float = 0.00015) -> bool:
        """
        Detects if market has flatlined or entered frozen consolidation.
        Ignores synthetic zero-volume fill bars so tick lulls do not lock out strategies.
        """
        if not candles:
            return False

        # Only evaluate genuine trading bars with volume
        genuine_bars = [c for c in candles if getattr(c, 'volume', 100.0) > 0.0]
        if len(genuine_bars) < lookback:
            return False

        recent = genuine_bars[-lookback:]
        highs = [c.high for c in recent]
        lows = [c.low for c in recent]
        max_h = max(highs)
        min_l = min(lows)
        base_price = recent[-1].close or 1.0

        if base_price <= 0:
            return False

        range_pct = (max_h - min_l) / base_price
        if range_pct < min_range_pct:
            return True

        zero_range_count = sum(1 for c in recent if abs(c.high - c.low) < (base_price * 0.00002))
        if zero_range_count >= 2:
            return True

        return False

    # -------------------------------------------------------------------------
    # Comprehensive Forex & Platform Indicator Catalog
    # -------------------------------------------------------------------------
    @staticmethod
    def calculate_wma(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Weighted Moving Average (WMA)."""
        if len(candles) < period:
            return None
        closes = [c.close for c in candles[-period:]]
        weights = list(range(1, period + 1))
        sum_weights = (period * (period + 1)) / 2
        return sum(c * w for c, w in zip(closes, weights)) / sum_weights

    @staticmethod
    def calculate_alligator(candles: List[Candle], jaw_p: int = 13, teeth_p: int = 8, lips_p: int = 5) -> Optional[Dict[str, float]]:
        """Bill Williams Alligator (Jaw, Teeth, Lips SMMA of Median Price)."""
        if len(candles) < jaw_p:
            return None
        medians = [(c.high + c.low) / 2.0 for c in candles]
        
        def _smma(series, p):
            val = sum(series[:p]) / p
            for x in series[p:]:
                val = (val * (p - 1) + x) / p
            return val

        return {
            "jaw": round(_smma(medians, jaw_p), 5),      # Blue line (13-period SMMA)
            "teeth": round(_smma(medians, teeth_p), 5),  # Red line (8-period SMMA)
            "lips": round(_smma(medians, lips_p), 5)     # Green line (5-period SMMA)
        }

    @staticmethod
    def calculate_envelopes(candles: List[Candle], period: int = 20, deviation_pct: float = 0.1) -> Optional[Dict[str, float]]:
        """Moving Average Envelopes."""
        if len(candles) < period:
            return None
        sma = sum(c.close for c in candles[-period:]) / period
        dev = sma * (deviation_pct / 100.0)
        return {
            "upper": round(sma + dev, 5),
            "middle": round(sma, 5),
            "lower": round(sma - dev, 5)
        }

    @staticmethod
    def calculate_fractal(candles: List[Candle]) -> Dict[str, Any]:
        """Bill Williams 5-Bar Geometric Fractals."""
        if len(candles) < 5:
            return {"is_bullish_fractal": False, "is_bearish_fractal": False, "fractal_high": None, "fractal_low": None}
        c = candles[-3]
        is_up = (c.high > candles[-5].high and c.high > candles[-4].high and c.high > candles[-2].high and c.high > candles[-1].high)
        is_down = (c.low < candles[-5].low and c.low < candles[-4].low and c.low < candles[-2].low and c.low < candles[-1].low)
        return {
            "is_bullish_fractal": is_down,  # Swing Low = Bullish reversal fractal
            "is_bearish_fractal": is_up,    # Swing High = Bearish reversal fractal
            "fractal_high": round(c.high, 5) if is_up else None,
            "fractal_low": round(c.low, 5) if is_down else None
        }

    @staticmethod
    def calculate_ichimoku(candles: List[Candle], tenkan_p: int = 9, kijun_p: int = 26, senkou_b_p: int = 52) -> Optional[Dict[str, float]]:
        """Ichimoku Kinko Hyo (Tenkan-sen, Kijun-sen, Senkou Span A & B)."""
        if len(candles) < senkou_b_p:
            return None
        
        def _mid_price(sub):
            return (max(c.high for c in sub) + min(c.low for c in sub)) / 2.0

        tenkan = _mid_price(candles[-tenkan_p:])
        kijun = _mid_price(candles[-kijun_p:])
        senkou_a = (tenkan + kijun) / 2.0
        senkou_b = _mid_price(candles[-senkou_b_p:])

        return {
            "tenkan_sen": round(tenkan, 5),
            "kijun_sen": round(kijun, 5),
            "senkou_span_a": round(senkou_a, 5),
            "senkou_span_b": round(senkou_b, 5),
            "cloud_bullish": senkou_a > senkou_b
        }

    @staticmethod
    def calculate_keltner_channel(candles: List[Candle], ema_p: int = 20, atr_p: int = 10, multiplier: float = 2.0) -> Optional[Dict[str, float]]:
        """Keltner Channel (EMA center with Wilder-smoothed ATR envelope)."""
        if len(candles) < max(ema_p, atr_p) + 1:
            return None
        closes = [c.close for c in candles]
        k = 2.0 / (ema_p + 1.0)
        ema = sum(closes[:ema_p]) / ema_p
        for p in closes[ema_p:]:
            ema = (p * k) + (ema * (1.0 - k))

        # Use Wilder's smoothed ATR instead of simple average
        true_ranges = [max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
                       for curr, prev in zip(candles[1:], candles[:-1])]
        if len(true_ranges) < atr_p:
            atr = candles[-1].high - candles[-1].low
        else:
            atr = sum(true_ranges[:atr_p]) / atr_p
            for tr in true_ranges[atr_p:]:
                atr = ((atr * (atr_p - 1)) + tr) / atr_p

        return {
            "upper": round(ema + (multiplier * atr), 5),
            "middle": round(ema, 5),
            "lower": round(ema - (multiplier * atr), 5)
        }

    @staticmethod
    def calculate_donchian_channel(candles: List[Candle], period: int = 20) -> Optional[Dict[str, float]]:
        """Donchian Channel (Highest High & Lowest Low)."""
        if len(candles) < period:
            return None
        sub = candles[-period:]
        upper = max(c.high for c in sub)
        lower = min(c.low for c in sub)
        return {
            "upper": round(upper, 5),
            "middle": round((upper + lower) / 2.0, 5),
            "lower": round(lower, 5)
        }

    @staticmethod
    def calculate_supertrend(candles: List[Candle], period: int = 10, multiplier: float = 3.0) -> Optional[Dict[str, Any]]:
        """
        Supertrend with proper band ratcheting and state flip tracking.
        Lower band can only rise (never decrease) during uptrend.
        Upper band can only fall (never increase) during downtrend.
        Trend flips when close crosses the active band.
        """
        if len(candles) < period + 2:
            return None

        # Build Wilder-smoothed ATR series
        true_ranges = [max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
                       for curr, prev in zip(candles[1:], candles[:-1])]
        if len(true_ranges) < period:
            return None
        atr_val = sum(true_ranges[:period]) / period
        atr_series = [0.0] * period
        atr_series.append(atr_val)
        for tr in true_ranges[period:]:
            atr_val = ((atr_val * (period - 1)) + tr) / period
            atr_series.append(atr_val)

        # Iterate with state tracking (starting from index period in the candles[1:] aligned data)
        # candles[0] has no TR, so candles[i+1] aligns with true_ranges[i] and atr_series[i]
        start_idx = period  # first bar where ATR is valid; corresponds to candles[start_idx + 1]
        is_uptrend = True
        prev_final_upper = float('inf')
        prev_final_lower = 0.0

        for j in range(start_idx, len(true_ranges)):
            c_idx = j + 1  # index into candles[]
            c = candles[c_idx]
            atr_now = atr_series[j]
            hl2 = (c.high + c.low) / 2.0

            basic_upper = hl2 + (multiplier * atr_now)
            basic_lower = hl2 - (multiplier * atr_now)

            # Ratchet: lower band can only rise, upper band can only fall
            final_lower = max(basic_lower, prev_final_lower) if candles[c_idx - 1].close > prev_final_lower else basic_lower
            final_upper = min(basic_upper, prev_final_upper) if candles[c_idx - 1].close < prev_final_upper else basic_upper

            # State flip
            if is_uptrend:
                if c.close < final_lower:
                    is_uptrend = False
            else:
                if c.close > final_upper:
                    is_uptrend = True

            prev_final_lower = final_lower
            prev_final_upper = final_upper

        st_val = prev_final_lower if is_uptrend else prev_final_upper
        prev_c = candles[-2]
        prev_was_uptrend_approx = prev_c.close > prev_final_lower  # approximate for flip detection
        trend_just_flipped = (is_uptrend != prev_was_uptrend_approx)

        return {
            "supertrend": round(st_val, 5),
            "trend": "BULLISH" if is_uptrend else "BEARISH",
            "upper_band": round(prev_final_upper, 5),
            "lower_band": round(prev_final_lower, 5),
            "trend_flipped": trend_just_flipped
        }

    @staticmethod
    def calculate_parabolic_sar(candles: List[Candle], step: float = 0.02, max_step: float = 0.2) -> Optional[Dict[str, Any]]:
        """
        Parabolic SAR with Wilder's clamping rule:
        In uptrend, SAR must not exceed lowest low of current or previous bar.
        In downtrend, SAR must not fall below highest high of current or previous bar.
        AF only increments when EP is updated (new extreme), not every bar.
        """
        if len(candles) < 5:
            return None

        is_bull = candles[1].close > candles[0].close
        sar = candles[0].low if is_bull else candles[0].high
        ep = candles[0].high if is_bull else candles[0].low
        af = step
        prev_trend = is_bull

        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]

            # Calculate new SAR
            new_sar = sar + af * (ep - sar)

            # Wilder's clamping: SAR must not penetrate prior 2-bar range
            if is_bull:
                # In uptrend, SAR cannot be above the low of current or previous bar
                new_sar = min(new_sar, prev.low)
                if i >= 2:
                    new_sar = min(new_sar, candles[i - 2].low)
            else:
                # In downtrend, SAR cannot be below the high of current or previous bar
                new_sar = max(new_sar, prev.high)
                if i >= 2:
                    new_sar = max(new_sar, candles[i - 2].high)

            sar = new_sar

            # Check for trend reversal
            if is_bull:
                if curr.low < sar:
                    # Flip to bearish
                    is_bull = False
                    sar = ep  # Reset SAR to extreme point of prior trend
                    ep = curr.low
                    af = step
                else:
                    # Update EP only when new high is made
                    if curr.high > ep:
                        ep = curr.high
                        af = min(max_step, af + step)
            else:
                if curr.high > sar:
                    # Flip to bullish
                    is_bull = True
                    sar = ep  # Reset SAR to extreme point of prior trend
                    ep = curr.high
                    af = step
                else:
                    # Update EP only when new low is made
                    if curr.low < ep:
                        ep = curr.low
                        af = min(max_step, af + step)

        trend_flipped = (is_bull != prev_trend)
        return {
            "sar": round(sar, 5),
            "trend": "BULLISH" if is_bull else "BEARISH",
            "is_bullish": is_bull,
            "trend_flipped": trend_flipped
        }

    @staticmethod
    def calculate_aroon(candles: List[Candle], period: int = 14) -> Optional[Dict[str, float]]:
        """Aroon Indicator (Aroon Up, Aroon Down, Aroon Oscillator)."""
        if len(candles) < period + 1:
            return None
        sub = candles[-period:]
        highs = [c.high for c in sub]
        lows = [c.low for c in sub]
        high_idx = period - 1 - highs.index(max(highs))
        low_idx = period - 1 - lows.index(min(lows))

        aroon_up = ((period - high_idx) / period) * 100.0
        aroon_down = ((period - low_idx) / period) * 100.0
        return {
            "aroon_up": round(aroon_up, 2),
            "aroon_down": round(aroon_down, 2),
            "oscillator": round(aroon_up - aroon_down, 2)
        }

    @staticmethod
    def calculate_awesome_oscillator(candles: List[Candle], fast_p: int = 5, slow_p: int = 34) -> Optional[Dict[str, Any]]:
        """Bill Williams Awesome Oscillator (AO)."""
        if len(candles) < slow_p:
            return None
        medians = [(c.high + c.low) / 2.0 for c in candles]
        fast_sma = sum(medians[-fast_p:]) / fast_p
        slow_sma = sum(medians[-slow_p:]) / slow_p
        ao = fast_sma - slow_sma

        prev_fast = sum(medians[-fast_p - 1:-1]) / fast_p
        prev_slow = sum(medians[-slow_p - 1:-1]) / slow_p
        prev_ao = prev_fast - prev_slow

        return {
            "ao": round(ao, 6),
            "prev_ao": round(prev_ao, 6),
            "color": "GREEN" if ao > prev_ao else "RED",
            "is_increasing": ao > prev_ao
        }

    @staticmethod
    def calculate_bulls_bears_power(candles: List[Candle], period: int = 13) -> Optional[Dict[str, float]]:
        """Elder-Ray Index (Bulls Power & Bears Power)."""
        if len(candles) < period:
            return None
        closes = [c.close for c in candles]
        k = 2.0 / (period + 1.0)
        ema = sum(closes[:period]) / period
        for p in closes[period:]:
            ema = (p * k) + (ema * (1.0 - k))
        
        last = candles[-1]
        return {
            "bulls_power": round(last.high - ema, 5),
            "bears_power": round(last.low - ema, 5),
            "ema": round(ema, 5)
        }

    @staticmethod
    def calculate_cci(candles: List[Candle], period: int = 20) -> Optional[float]:
        """Commodity Channel Index (CCI)."""
        if len(candles) < period:
            return None
        typical_prices = [(c.high + c.low + c.close) / 3.0 for c in candles[-period:]]
        mean_tp = sum(typical_prices) / period
        mean_deviation = sum(abs(x - mean_tp) for x in typical_prices) / period
        if mean_deviation == 0:
            return 0.0
        cci = (typical_prices[-1] - mean_tp) / (0.015 * mean_deviation)
        return round(cci, 2)

    @staticmethod
    def calculate_demarker(candles: List[Candle], period: int = 14) -> Optional[float]:
        """DeMarker Oscillator (DeM)."""
        if len(candles) < period + 1:
            return None
        de_max = []
        de_min = []
        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]
            de_max.append(max(0.0, curr.high - prev.high))
            de_min.append(max(0.0, prev.low - curr.low))
        
        avg_max = sum(de_max[-period:]) / period
        avg_min = sum(de_min[-period:]) / period
        total = avg_max + avg_min
        return round(avg_max / total, 4) if total > 0 else 0.5

    @staticmethod
    def calculate_momentum(candles: List[Candle], period: int = 10) -> Optional[float]:
        """Momentum Oscillator."""
        if len(candles) < period + 1:
            return None
        return round(candles[-1].close - candles[-period - 1].close, 5)

    @staticmethod
    def calculate_rate_of_change(candles: List[Candle], period: int = 10) -> Optional[float]:
        """Rate of Change (ROC %)."""
        if len(candles) < period + 1:
            return None
        prev_close = candles[-period - 1].close
        if prev_close == 0:
            return 0.0
        roc = ((candles[-1].close - prev_close) / prev_close) * 100.0
        return round(roc, 2)

    @staticmethod
    def calculate_williams_r(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Williams %R Oscillator (-100 to 0)."""
        if len(candles) < period:
            return None
        sub = candles[-period:]
        highest_high = max(c.high for c in sub)
        lowest_low = min(c.low for c in sub)
        rng = highest_high - lowest_low
        if rng == 0:
            return -50.0
        wr = ((highest_high - sub[-1].close) / rng) * -100.0
        return round(wr, 2)

    @staticmethod
    def calculate_vortex(candles: List[Candle], period: int = 14) -> Optional[Dict[str, float]]:
        """Vortex Indicator (+VI, -VI)."""
        if len(candles) < period + 1:
            return None
        vm_plus = []
        vm_minus = []
        tr_list = []
        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]
            vm_plus.append(abs(curr.high - prev.low))
            vm_minus.append(abs(curr.low - prev.high))
            tr = max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
            tr_list.append(tr)

        sum_tr = sum(tr_list[-period:])
        if sum_tr == 0:
            return {"plus_vi": 1.0, "minus_vi": 1.0}
        
        plus_vi = sum(vm_plus[-period:]) / sum_tr
        minus_vi = sum(vm_minus[-period:]) / sum_tr
        return {
            "plus_vi": round(plus_vi, 4),
            "minus_vi": round(minus_vi, 4),
            "bullish_cross": plus_vi > minus_vi
        }

    @staticmethod
    def calculate_volume_oscillator(candles: List[Candle], short_p: int = 5, long_p: int = 10) -> Optional[float]:
        """Volume Oscillator (% difference between short and long Volume EMAs using true EMA)."""
        if len(candles) < long_p:
            return None
        vols = [c.volume for c in candles]

        # Compute true EMA for short period
        k_short = 2.0 / (short_p + 1.0)
        short_ema = sum(vols[:short_p]) / short_p
        for v in vols[short_p:]:
            short_ema = (v * k_short) + (short_ema * (1.0 - k_short))

        # Compute true EMA for long period
        k_long = 2.0 / (long_p + 1.0)
        long_ema = sum(vols[:long_p]) / long_p
        for v in vols[long_p:]:
            long_ema = (v * k_long) + (long_ema * (1.0 - k_long))

        if long_ema == 0:
            return 0.0
        vo = ((short_ema - long_ema) / long_ema) * 100.0
        return round(vo, 2)

    @classmethod
    def calculate_technical_snapshot(cls, candles: List[Candle]) -> Dict[str, Any]:
        """Calculates a complete multi-indicator snapshot across all Forex indicators in a single pass."""
        if not candles:
            return {}

        current_price = candles[-1].close
        sma_200 = cls.calculate_sma(candles, 200) or cls.calculate_sma(candles, min(len(candles), 50))
        ema_fast = cls.calculate_ema(candles, 9)
        ema_slow = cls.calculate_ema(candles, 21)
        ema_20 = cls.calculate_ema(candles, 20)
        ema_50 = cls.calculate_ema(candles, 50)
        ema_200 = cls.calculate_ema(candles, 200) or cls.calculate_ema(candles, min(len(candles), 50))

        trend = "NEUTRAL"
        if ema_fast and ema_slow:
            if ema_fast > ema_slow and current_price > ema_fast:
                trend = "BULLISH"
            elif ema_fast < ema_slow and current_price < ema_fast:
                trend = "BEARISH"

        support, resistance = cls.find_support_resistance_levels(candles)
        recent_volumes = [c.volume for c in candles[-20:]]
        avg_vol = (sum(recent_volumes) / len(recent_volumes)) if recent_volumes else 100.0
        vol_ratio = (candles[-1].volume / avg_vol) if avg_vol > 0 else 1.0
        streak_color, streak_count = cls.calculate_consecutive_streak(candles)

        return {
            "current_price": current_price,
            "trend": trend,
            "rsi": cls.calculate_rsi(candles, 14),
            "rsi_7": cls.calculate_rsi(candles, 7),
            "sma_10": cls.calculate_sma(candles, 10),
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_200": ema_200,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "sma_200": sma_200,
            "macd": cls.calculate_macd(candles),
            "bollinger_bands": cls.calculate_bollinger_bands(candles, 20),
            "atr": cls.calculate_atr(candles, 14),
            "adx": cls.calculate_adx(candles, 14),
            "stochastic": cls.calculate_stochastic(candles, 14, 3),
            "streak_color": streak_color,
            "streak_count": streak_count,
            "vwap": cls.calculate_vwap(candles),
            "vwap_30": cls.calculate_vwap(candles[-30:]),
            "volume_ratio": round(vol_ratio, 2),
            "support_levels": support,
            "resistance_levels": resistance,
            "nearest_support": support[-1] if support else None,
            "nearest_resistance": resistance[-1] if resistance else None,
            "is_flatlined": cls.is_market_flatlined(candles),
            
            # Additional Forex Indicators from Quotex/TradingView
            "alligator": cls.calculate_alligator(candles),
            "envelopes": cls.calculate_envelopes(candles),
            "fractal": cls.calculate_fractal(candles),
            "ichimoku": cls.calculate_ichimoku(candles),
            "keltner": cls.calculate_keltner_channel(candles),
            "donchian": cls.calculate_donchian_channel(candles),
            "supertrend": cls.calculate_supertrend(candles),
            "parabolic_sar": cls.calculate_parabolic_sar(candles),
            "aroon": cls.calculate_aroon(candles),
            "awesome_oscillator": cls.calculate_awesome_oscillator(candles),
            "bulls_bears_power": cls.calculate_bulls_bears_power(candles),
            "cci": cls.calculate_cci(candles),
            "demarker": cls.calculate_demarker(candles),
            "momentum": cls.calculate_momentum(candles),
            "roc": cls.calculate_rate_of_change(candles),
            "williams_r": cls.calculate_williams_r(candles),
            "vortex": cls.calculate_vortex(candles),
            "volume_oscillator": cls.calculate_volume_oscillator(candles),
            "formations": cls.calculate_candlestick_formations(candles),
            "smc_structure": cls.calculate_smc_structure(candles),
        }

    # -------------------------------------------------------------------------
    # Candlestick Formations & Price Action Pattern Recognition Engine
    # -------------------------------------------------------------------------
    @staticmethod
    def calculate_candlestick_formations(candles: List[Candle]) -> Dict[str, Any]:
        """
        Recognizes key single-bar, two-bar, and three-bar candlestick formations
        (Pinbar/Hammer, Engulfing, Morning/Evening Star, Three Soldiers/Crows, Inside Bar, Tweezer).
        """
        if not candles or len(candles) < 2:
            return {
                "pinbar_bullish": False, "pinbar_bearish": False,
                "engulfing_bullish": False, "engulfing_bearish": False,
                "morning_star": False, "evening_star": False,
                "three_white_soldiers": False, "three_black_crows": False,
                "inside_bar": False, "tweezer_top": False, "tweezer_bottom": False,
                "doji": False, "detected_patterns": []
            }

        detected = []
        c = candles[-1]
        prev = candles[-2]
        
        c_range = max(1e-6, c.high - c.low)
        c_body = abs(c.close - c.open)
        c_upper_wick = c.high - max(c.open, c.close)
        c_lower_wick = min(c.open, c.close) - c.low

        prev_range = max(1e-6, prev.high - prev.low)
        prev_body = abs(prev.close - prev.open)

        # 1. Pinbar / Hammer / Shooting Star
        pinbar_bull = (c_lower_wick >= (0.55 * c_range)) and (c_body <= (0.35 * c_range)) and (c_upper_wick <= (0.25 * c_range))
        pinbar_bear = (c_upper_wick >= (0.55 * c_range)) and (c_body <= (0.35 * c_range)) and (c_lower_wick <= (0.25 * c_range))
        if pinbar_bull: detected.append("BULLISH_PINBAR")
        if pinbar_bear: detected.append("BEARISH_PINBAR")

        # 2. Bullish & Bearish Engulfing
        engulfing_bull = (
            prev.is_bearish and c.is_bullish and
            c.close >= prev.open and c.open <= prev.close and
            (c_body >= 0.55 * c_range)
        )
        engulfing_bear = (
            prev.is_bullish and c.is_bearish and
            c.close <= prev.open and c.open >= prev.close and
            (c_body >= 0.55 * c_range)
        )
        if engulfing_bull: detected.append("BULLISH_ENGULFING")
        if engulfing_bear: detected.append("BEARISH_ENGULFING")

        # 3. Inside Bar (Harami)
        inside_bar = (c.high <= prev.high) and (c.low >= prev.low)
        if inside_bar: detected.append("INSIDE_BAR")

        # 4. Tweezer Tops / Bottoms
        tweezer_top = (abs(c.high - prev.high) <= (c_range * 0.05)) and prev.is_bullish and c.is_bearish and (c_upper_wick >= 0.3 * c_range)
        tweezer_bot = (abs(c.low - prev.low) <= (c_range * 0.05)) and prev.is_bearish and c.is_bullish and (c_lower_wick >= 0.3 * c_range)
        if tweezer_top: detected.append("TWEEZER_TOP")
        if tweezer_bot: detected.append("TWEEZER_BOTTOM")

        # 5. Doji
        doji = (c_body / c_range) < 0.10
        if doji: detected.append("DOJI")

        # 6. Three-Bar Formations (Morning Star, Evening Star, Three Soldiers, Three Crows)
        morning_star = False
        evening_star = False
        three_soldiers = False
        three_crows = False

        if len(candles) >= 3:
            p2 = candles[-3]
            p2_range = max(1e-6, p2.high - p2.low)
            p2_body = abs(p2.close - p2.open)

            # Morning Star (Bearish bar -> small body/doji -> Bullish bar closing past mid of bar 1)
            if p2.is_bearish and (p2_body >= 0.5 * p2_range):
                if (prev_body <= 0.35 * prev_range) and c.is_bullish and (c.close >= (p2.open + p2.close) / 2.0):
                    morning_star = True
                    detected.append("MORNING_STAR")

            # Evening Star (Bullish bar -> small body/doji -> Bearish bar closing past mid of bar 1)
            if p2.is_bullish and (p2_body >= 0.5 * p2_range):
                if (prev_body <= 0.35 * prev_range) and c.is_bearish and (c.close <= (p2.open + p2.close) / 2.0):
                    evening_star = True
                    detected.append("EVENING_STAR")

            # Three White Soldiers
            if p2.is_bullish and prev.is_bullish and c.is_bullish:
                if (c.close > prev.close > p2.close) and (c_body > 0.5 * c_range) and (prev_body > 0.5 * prev_range):
                    three_soldiers = True
                    detected.append("THREE_WHITE_SOLDIERS")

            # Three Black Crows
            if p2.is_bearish and prev.is_bearish and c.is_bearish:
                if (c.close < prev.close < p2.close) and (c_body > 0.5 * c_range) and (prev_body > 0.5 * prev_range):
                    three_crows = True
                    detected.append("THREE_BLACK_CROWS")

        return {
            "pinbar_bullish": pinbar_bull,
            "pinbar_bearish": pinbar_bear,
            "engulfing_bullish": engulfing_bull,
            "engulfing_bearish": engulfing_bear,
            "morning_star": morning_star,
            "evening_star": evening_star,
            "three_white_soldiers": three_soldiers,
            "three_black_crows": three_crows,
            "inside_bar": inside_bar,
            "tweezer_top": tweezer_top,
            "tweezer_bottom": tweezer_bot,
            "doji": doji,
            "detected_patterns": detected
        }

    @staticmethod
    def calculate_smc_structure(candles: List[Candle], swing_lookback: int = 3) -> Dict[str, Any]:
        """
        Smart Money Concepts (SMC) market structure engine:
        Calculates Break of Structure (BOS), Change of Character (CHOCH),
        Fair Value Gaps (FVG), Liquidity Sweeps, and Swing Highs/Lows.
        """
        if len(candles) < (swing_lookback * 2) + 2:
            return {
                "bos_bullish": False, "bos_bearish": False,
                "choch_bullish": False, "choch_bearish": False,
                "fvg_bullish": False, "fvg_bearish": False,
                "liquidity_sweep_bullish": False, "liquidity_sweep_bearish": False,
                "last_swing_high": None, "last_swing_low": None,
                "structure_trend": "NEUTRAL"
            }

        n = len(candles)
        swing_highs = []
        swing_lows = []

        # Find recent confirmed swing points (excluding last few unconfirmed bars)
        for i in range(swing_lookback, n - swing_lookback - 1):
            curr = candles[i]
            if all(candles[j].high < curr.high for j in range(i - swing_lookback, i + swing_lookback + 1) if j != i):
                swing_highs.append((i, curr.high))
            if all(candles[j].low > curr.low for j in range(i - swing_lookback, i + swing_lookback + 1) if j != i):
                swing_lows.append((i, curr.low))

        last_sh = swing_highs[-1][1] if swing_highs else None
        last_sl = swing_lows[-1][1] if swing_lows else None

        c = candles[-1]
        prev = candles[-2]

        # Break of Structure (BOS): Body close strictly breaks prior swing level in trend direction
        bos_bullish = (last_sh is not None) and (c.close > last_sh) and (prev.close <= last_sh)
        bos_bearish = (last_sl is not None) and (c.close < last_sl) and (prev.close >= last_sl)

        # Change of Character (CHOCH): First structural break counter to prevailing swing series
        choch_bullish = False
        choch_bearish = False
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            prev_sh = swing_highs[-2][1]
            prev_sl = swing_lows[-2][1]
            is_downtrend = (last_sh < prev_sh) and (last_sl < prev_sl)
            is_uptrend = (last_sh > prev_sh) and (last_sl > prev_sl)
            
            if is_downtrend and (c.close > last_sh):
                choch_bullish = True
            if is_uptrend and (c.close < last_sl):
                choch_bearish = True

        # Fair Value Gap (FVG): Imbalance between bar[i-2] and bar[i]
        fvg_bullish = False
        fvg_bearish = False
        if len(candles) >= 3:
            p2 = candles[-3]
            # Bullish FVG: Bar 1 High < Bar 3 Low
            if c.low > p2.high:
                fvg_bullish = True
            # Bearish FVG: Bar 1 Low > Bar 3 High
            if c.high < p2.low:
                fvg_bearish = True

        # Liquidity Sweep: Wick pierced past swing level but candle body closed back inside
        liq_sweep_bull = (last_sl is not None) and (c.low < last_sl) and (c.close > last_sl) and (c.is_bullish or c.close > c.open)
        liq_sweep_bear = (last_sh is not None) and (c.high > last_sh) and (c.close < last_sh) and (c.is_bearish or c.close < c.open)

        struct_trend = "NEUTRAL"
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            if swing_highs[-1][1] > swing_highs[-2][1] and swing_lows[-1][1] > swing_lows[-2][1]:
                struct_trend = "BULLISH"
            elif swing_highs[-1][1] < swing_highs[-2][1] and swing_lows[-1][1] < swing_lows[-2][1]:
                struct_trend = "BEARISH"

        return {
            "bos_bullish": bos_bullish,
            "bos_bearish": bos_bearish,
            "choch_bullish": choch_bullish,
            "choch_bearish": choch_bearish,
            "fvg_bullish": fvg_bullish,
            "fvg_bearish": fvg_bearish,
            "liquidity_sweep_bullish": liq_sweep_bull,
            "liquidity_sweep_bearish": liq_sweep_bear,
            "last_swing_high": round(last_sh, 5) if last_sh else None,
            "last_swing_low": round(last_sl, 5) if last_sl else None,
            "structure_trend": struct_trend
        }


