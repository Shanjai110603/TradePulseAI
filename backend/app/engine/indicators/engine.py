import math
from typing import List, Dict, Any, Optional, Tuple
from app.engine.market_data.base import Candle


class TechnicalIndicatorEngine:
    """
    High-performance, deterministic technical indicator calculation engine.
    Never relies on external black-boxes or LLMs for mathematical formulas.
    """

    @staticmethod
    def calculate_sma(prices: List[float], period: int = 14) -> List[Optional[float]]:
        if len(prices) < period:
            return [None] * len(prices)
        result: List[Optional[float]] = [None] * (period - 1)
        current_sum = sum(prices[:period])
        result.append(current_sum / period)

        for i in range(period, len(prices)):
            current_sum += prices[i] - prices[i - period]
            result.append(current_sum / period)
        return result

    @staticmethod
    def calculate_ema(prices: List[float], period: int = 14) -> List[Optional[float]]:
        if len(prices) < period:
            return [None] * len(prices)
        result: List[Optional[float]] = [None] * (period - 1)
        
        # Initial SMA
        multiplier = 2.0 / (period + 1)
        initial_sma = sum(prices[:period]) / period
        result.append(initial_sma)
        
        current_ema = initial_sma
        for i in range(period, len(prices)):
            current_ema = (prices[i] - current_ema) * multiplier + current_ema
            result.append(current_ema)
        return result

    @classmethod
    def calculate_rsi(cls, candles: List[Candle], period: int = 14) -> List[Optional[float]]:
        if len(candles) <= period:
            return [None] * len(candles)

        closes = [c.close for c in candles]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        
        gains = [max(d, 0.0) for d in deltas]
        losses = [abs(min(d, 0.0)) for d in deltas]

        result: List[Optional[float]] = [None] * period

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - (100.0 / (1.0 + rs)))

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100.0 - (100.0 / (1.0 + rs)))

        return result

    @classmethod
    def calculate_macd(
        cls,
        candles: List[Candle],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, List[Optional[float]]]:
        closes = [c.close for c in candles]
        ema_fast = cls.calculate_ema(closes, fast_period)
        ema_slow = cls.calculate_ema(closes, slow_period)

        macd_line: List[Optional[float]] = []
        for f, s in zip(ema_fast, ema_slow):
            if f is not None and s is not None:
                macd_line.append(f - s)
            else:
                macd_line.append(None)

        # Signal line is EMA of MACD line (ignoring initial None values)
        valid_macd = [v for v in macd_line if v is not None]
        none_count = len(macd_line) - len(valid_macd)

        if len(valid_macd) >= signal_period:
            signal_valid = cls.calculate_ema(valid_macd, signal_period)
            signal_line = ([None] * none_count) + signal_valid
        else:
            signal_line = [None] * len(candles)

        histogram: List[Optional[float]] = []
        for m, s in zip(macd_line, signal_line):
            if m is not None and s is not None:
                histogram.append(m - s)
            else:
                histogram.append(None)

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }

    @classmethod
    def calculate_bollinger_bands(
        cls,
        candles: List[Candle],
        period: int = 20,
        num_std_dev: float = 2.0
    ) -> Dict[str, List[Optional[float]]]:
        closes = [c.close for c in candles]
        sma = cls.calculate_sma(closes, period)
        upper: List[Optional[float]] = [None] * len(candles)
        lower: List[Optional[float]] = [None] * len(candles)
        percent_b: List[Optional[float]] = [None] * len(candles)

        for i in range(period - 1, len(closes)):
            window = closes[i - period + 1 : i + 1]
            mean = sma[i]
            if mean is not None:
                variance = sum((x - mean) ** 2 for x in window) / period
                std_dev = math.sqrt(variance)
                u = mean + (num_std_dev * std_dev)
                l = mean - (num_std_dev * std_dev)
                upper[i] = u
                lower[i] = l
                percent_b[i] = (closes[i] - l) / max(u - l, 1e-8)

        return {
            "middle": sma,
            "upper": upper,
            "lower": lower,
            "percent_b": percent_b
        }

    @classmethod
    def calculate_atr(cls, candles: List[Candle], period: int = 14) -> List[Optional[float]]:
        if len(candles) < 2:
            return [None] * len(candles)

        tr_list: List[float] = [candles[0].high - candles[0].low]
        for i in range(1, len(candles)):
            c = candles[i]
            prev_close = candles[i - 1].close
            tr = max(
                c.high - c.low,
                abs(c.high - prev_close),
                abs(c.low - prev_close)
            )
            tr_list.append(tr)

        if len(tr_list) < period:
            return [None] * len(candles)

        atr_list: List[Optional[float]] = [None] * (period - 1)
        initial_atr = sum(tr_list[:period]) / period
        atr_list.append(initial_atr)

        current_atr = initial_atr
        for i in range(period, len(tr_list)):
            current_atr = (current_atr * (period - 1) + tr_list[i]) / period
            atr_list.append(current_atr)

        return atr_list

    @classmethod
    def calculate_adx(cls, candles: List[Candle], period: int = 14) -> Dict[str, List[Optional[float]]]:
        if len(candles) < period * 2:
            return {
                "adx": [None] * len(candles),
                "plus_di": [None] * len(candles),
                "minus_di": [None] * len(candles)
            }

        atr = cls.calculate_atr(candles, period)
        plus_dm: List[float] = [0.0]
        minus_dm: List[float] = [0.0]

        for i in range(1, len(candles)):
            up_move = candles[i].high - candles[i - 1].high
            down_move = candles[i - 1].low - candles[i].low

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0.0)

            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0.0)

        # Smoothed DM
        smooth_plus = cls.calculate_ema(plus_dm, period)
        smooth_minus = cls.calculate_ema(minus_dm, period)

        plus_di: List[Optional[float]] = [None] * len(candles)
        minus_di: List[Optional[float]] = [None] * len(candles)
        dx: List[Optional[float]] = [None] * len(candles)

        for i in range(len(candles)):
            a = atr[i]
            sp = smooth_plus[i]
            sm = smooth_minus[i]
            if a is not None and sp is not None and sm is not None and a > 0:
                p_di = (sp / a) * 100.0
                m_di = (sm / a) * 100.0
                plus_di[i] = p_di
                minus_di[i] = m_di
                di_sum = p_di + m_di
                if di_sum > 0:
                    dx[i] = (abs(p_di - m_di) / di_sum) * 100.0

        valid_dx = [x for x in dx if x is not None]
        none_count = len(dx) - len(valid_dx)
        if len(valid_dx) >= period:
            adx_valid = cls.calculate_ema(valid_dx, period)
            adx = ([None] * none_count) + adx_valid
        else:
            adx = [None] * len(candles)

        return {
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di
        }

    @classmethod
    def calculate_stochastic(
        cls,
        candles: List[Candle],
        k_period: int = 14,
        d_period: int = 3
    ) -> Dict[str, List[Optional[float]]]:
        k_line: List[Optional[float]] = [None] * len(candles)

        for i in range(k_period - 1, len(candles)):
            window = candles[i - k_period + 1 : i + 1]
            lowest_low = min(c.low for c in window)
            highest_high = max(c.high for c in window)
            curr_close = candles[i].close

            rng = highest_high - lowest_low
            if rng > 0:
                k_line[i] = ((curr_close - lowest_low) / rng) * 100.0
            else:
                k_line[i] = 50.0

        valid_k = [x for x in k_line if x is not None]
        none_count = len(k_line) - len(valid_k)

        if len(valid_k) >= d_period:
            d_valid = cls.calculate_sma(valid_k, d_period)
            d_line = ([None] * none_count) + d_valid
        else:
            d_line = [None] * len(candles)

        return {"k": k_line, "d": d_line}

    @classmethod
    def calculate_vwap(cls, candles: List[Candle]) -> List[Optional[float]]:
        cum_pv = 0.0
        cum_vol = 0.0
        vwap: List[Optional[float]] = []

        for c in candles:
            typical_price = (c.high + c.low + c.close) / 3.0
            cum_pv += typical_price * c.volume
            cum_vol += c.volume
            vwap.append(cum_pv / cum_vol if cum_vol > 0 else c.close)
        return vwap

    @classmethod
    def find_support_resistance_levels(
        cls,
        candles: List[Candle],
        lookback: int = 5
    ) -> Tuple[List[float], List[float]]:
        """Identifies swing lows (supports) and swing highs (resistances)"""
        supports: List[float] = []
        resistances: List[float] = []

        if len(candles) < (lookback * 2 + 1):
            return supports, resistances

        for i in range(lookback, len(candles) - lookback):
            current = candles[i]
            # Check swing high
            is_high = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and candles[j].high >= current.high:
                    is_high = False
                    break
            if is_high:
                resistances.append(current.high)

            # Check swing low
            is_low = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and candles[j].low <= current.low:
                    is_low = False
                    break
            if is_low:
                supports.append(current.low)

        return sorted(list(set(supports))), sorted(list(set(resistances)))

    @classmethod
    def calculate_technical_snapshot(cls, candles: List[Candle]) -> Dict[str, Any]:
        """Calculates a comprehensive technical snapshot dictionary from current candles"""
        if not candles:
            return {}

        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]

        rsi_series = cls.calculate_rsi(candles, 14)
        macd_dict = cls.calculate_macd(candles, 12, 26, 9)
        ema_fast = cls.calculate_ema(closes, 9)
        ema_slow = cls.calculate_ema(closes, 21)
        sma_200 = cls.calculate_sma(closes, 50 if len(closes) < 200 else 200)
        bb_dict = cls.calculate_bollinger_bands(candles, 20, 2.0)
        atr_series = cls.calculate_atr(candles, 14)
        adx_dict = cls.calculate_adx(candles, 14)
        stoch_dict = cls.calculate_stochastic(candles, 14, 3)
        vwap_series = cls.calculate_vwap(candles)
        vol_sma = cls.calculate_sma(volumes, 20)
        supports, resistances = cls.find_support_resistance_levels(candles, 3)

        curr_vol = volumes[-1] if volumes else 0
        avg_vol = vol_sma[-1] if vol_sma and vol_sma[-1] else curr_vol
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

        # Market structure & Trend
        last_close = closes[-1]
        fast_val = ema_fast[-1]
        slow_val = ema_slow[-1]
        
        if fast_val and slow_val:
            if fast_val > slow_val and last_close > fast_val:
                trend = "BULLISH"
            elif fast_val < slow_val and last_close < fast_val:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
        else:
            trend = "NEUTRAL"

        return {
            "rsi": round(rsi_series[-1], 2) if rsi_series[-1] is not None else None,
            "macd": {
                "macd": round(macd_dict["macd"][-1], 5) if macd_dict["macd"][-1] is not None else None,
                "signal": round(macd_dict["signal"][-1], 5) if macd_dict["signal"][-1] is not None else None,
                "histogram": round(macd_dict["histogram"][-1], 5) if macd_dict["histogram"][-1] is not None else None,
            },
            "ema_fast": round(ema_fast[-1], 5) if ema_fast[-1] is not None else None,
            "ema_slow": round(ema_slow[-1], 5) if ema_slow[-1] is not None else None,
            "sma_200": round(sma_200[-1], 5) if sma_200[-1] is not None else None,
            "bollinger_bands": {
                "upper": round(bb_dict["upper"][-1], 5) if bb_dict["upper"][-1] is not None else None,
                "middle": round(bb_dict["middle"][-1], 5) if bb_dict["middle"][-1] is not None else None,
                "lower": round(bb_dict["lower"][-1], 5) if bb_dict["lower"][-1] is not None else None,
                "percent_b": round(bb_dict["percent_b"][-1], 3) if bb_dict["percent_b"][-1] is not None else None,
            },
            "atr": round(atr_series[-1], 5) if atr_series[-1] is not None else None,
            "adx": round(adx_dict["adx"][-1], 2) if adx_dict["adx"][-1] is not None else None,
            "stochastic": {
                "k": round(stoch_dict["k"][-1], 2) if stoch_dict["k"][-1] is not None else None,
                "d": round(stoch_dict["d"][-1], 2) if stoch_dict["d"][-1] is not None else None,
            },
            "vwap": round(vwap_series[-1], 5) if vwap_series[-1] is not None else None,
            "volume_ratio": round(vol_ratio, 2),
            "support_levels": [round(s, 5) for s in supports[-5:]],
            "resistance_levels": [round(r, 5) for r in resistances[-5:]],
            "market_structure": {
                "trend": trend,
                "current_price": last_close,
            }
        }
