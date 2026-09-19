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
        """Bollinger Bands (Upper, Middle, Lower, %B)."""
        if len(candles) < period:
            return None

        closes = [c.close for c in candles[-period:]]
        mean = sum(closes) / period
        variance = sum((x - mean) ** 2 for x in closes) / period
        std_dev = math.sqrt(variance)

        upper = mean + (std_dev_multiplier * std_dev)
        lower = mean - (std_dev_multiplier * std_dev)
        current = closes[-1]
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
            return [c.low for c in candles[-3:]], [c.high for c in candles[-3:]]

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
        Returns True if total price movement across the lookback bars is below min_range_pct
        or if candles form identical doji lines (common in low-liquidity OTC flatlines).
        """
        if not candles or len(candles) < lookback:
            return False

        recent = candles[-lookback:]
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

    @classmethod
    def calculate_technical_snapshot(cls, candles: List[Candle]) -> Dict[str, Any]:
        """Calculates a complete multi-indicator snapshot in a single pass."""
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
            "vwap": cls.calculate_vwap(candles),  # Full available session buffer
            "vwap_30": cls.calculate_vwap(candles[-30:]),  # Explicit rolling 30-bar VWAP
            "volume_ratio": round(vol_ratio, 2),
            "support_levels": support,
            "resistance_levels": resistance,
            "nearest_support": support[-1] if support else None,
            "nearest_resistance": resistance[-1] if resistance else None,
            "is_flatlined": cls.is_market_flatlined(candles),
        }
