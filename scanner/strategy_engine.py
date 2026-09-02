"""
TradePulse Strategy Engine — Deterministic Multi-Engine & Explainability Evaluator
===================================================================================
Evaluates Strategy 1 (MTF_ENGULFING_1M) with:
 - Multi-timeframe 1M and 5M aggregation
 - Exponential Moving Average (EMA 20) trend alignment
 - Strict candle proportion checks (> 65% solid body, <= 30% opposing wick)
 - Doji rejection & Anomaly spike filters
 - Transparent Explainability Confidence Breakdown
"""

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 100.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def total_range(self) -> float:
        return max(self.high - self.low, 1e-8)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


class StrategyEngine:
    """Deterministic, high-speed confluence evaluator for Quotex binary options."""

    @staticmethod
    def compute_ema(values: List[float], period: int = 20) -> float:
        if not values:
            return 0.0
        p = min(period, len(values))
        if p <= 1:
            return values[-1]
        k = 2.0 / (p + 1)
        ema = values[0]
        for v in values[1:]:
            ema = v * k + ema * (1.0 - k)
        return ema

    @staticmethod
    def aggregate_to_5m(candles_1m: List[Candle]) -> List[Candle]:
        """Compresses 1M candles into 5-minute bars."""
        if len(candles_1m) < 5:
            return candles_1m[-1:] if candles_1m else []
        res = []
        for i in range(0, len(candles_1m) - 4, 5):
            group = candles_1m[i : i + 5]
            if len(group) >= 2:
                res.append(Candle(
                    timestamp=group[0].timestamp,
                    open=group[0].open,
                    high=max(c.high for c in group),
                    low=min(c.low for c in group),
                    close=group[-1].close,
                    volume=sum(c.volume for c in group)
                ))
        rem = len(candles_1m) % 5
        if rem > 0:
            group = candles_1m[-rem:]
            res.append(Candle(
                timestamp=group[0].timestamp,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group)
            ))
        return res

    @classmethod
    def evaluate_mtf_engulfing(
        cls,
        candles_1m: List[Candle],
        payout_pct: float = 85.0
    ) -> Tuple[bool, str, Dict]:
        """
        Evaluates MTF_ENGULFING_1M strategy.
        Returns: (matched: bool, reason: str, details: Dict)
        """
        breakdown = {
            "payout_check": False,
            "candle_count_check": False,
            "doji_check": False,
            "body_ratio_check": False,
            "wick_check": False,
            "spike_check": False,
            "trend_5m_check": False,
            "engulfing_1m_check": False,
            "confidence_score": 0,
        }

        # 1. Payout Filter (>= 80%)
        if payout_pct < 80:
            return False, f"Payout {payout_pct}% < 80% minimum threshold", breakdown
        breakdown["payout_check"] = True

        if len(candles_1m) < 6:
            return False, f"Insufficient candle history ({len(candles_1m)}/6 required)", breakdown
        breakdown["candle_count_check"] = True

        c = candles_1m[-1]
        prev = candles_1m[-2]

        rng_c = c.total_range
        body_c = c.body_size
        upper_wick_c = c.upper_wick
        lower_wick_c = c.lower_wick

        rng_prev = prev.total_range
        body_prev = prev.body_size

        # 2. Avoid Doji on preceding bar (body >= 10% of range)
        prev_body_ratio = body_prev / rng_prev
        if prev_body_ratio < 0.10:
            return False, f"Preceding candle is a Doji ({prev_body_ratio*100:.1f}% < 10%)", breakdown
        breakdown["doji_check"] = True

        # 3. Solid Body on 1M trigger candle (> 65% of total range)
        body_ratio = body_c / rng_c
        if body_ratio <= 0.65:
            return False, f"Trigger candle body ({body_ratio*100:.1f}%) <= 65% requirement", breakdown
        breakdown["body_ratio_check"] = True

        # 4. Anomaly Spike Filter (<= 3x average of previous 3 bars)
        if len(candles_1m) >= 5:
            avg_3 = sum(k.total_range for k in candles_1m[-4:-1]) / 3.0
            if rng_c > (3.0 * avg_3):
                return False, f"Anomaly spike detected: range {rng_c:.5f} > 3x average ({avg_3:.5f})", breakdown
        breakdown["spike_check"] = True

        # 5. Multi-Timeframe 5M Trend & EMA 20
        candles_5m = cls.aggregate_to_5m(candles_1m)
        c_5m = candles_5m[-1] if candles_5m else c
        ema_20_5m = cls.compute_ema([b.close for b in candles_5m], period=20)
        ema_20_1m = cls.compute_ema([b.close for b in candles_1m], period=20)

        # 6. Directional Confluence: CALL (UP)
        cond_5m_call = c_5m.is_bullish and (c_5m.close > ema_20_5m)
        cond_1m_bull_engulf = (
            c.is_bullish and prev.is_bearish and
            c.open <= (prev.close + 1e-4) and
            c.close >= (prev.open - 1e-4) and
            c.close > prev.high
        )
        cond_1m_ema_call = c.close > ema_20_1m
        upper_wick_ratio = upper_wick_c / rng_c
        wick_ok_call = upper_wick_ratio <= 0.30

        # 7. Directional Confluence: PUT (DOWN)
        cond_5m_put = c_5m.is_bearish and (c_5m.close < ema_20_5m)
        cond_1m_bear_engulf = (
            c.is_bearish and prev.is_bullish and
            c.open >= (prev.close - 1e-4) and
            c.close <= (prev.open + 1e-4) and
            c.close < prev.low
        )
        cond_1m_ema_put = c.close < ema_20_1m
        lower_wick_ratio = lower_wick_c / rng_c
        wick_ok_put = lower_wick_ratio <= 0.30

        # Populate breakdown for explainability
        breakdown["trend_5m_check"] = cond_5m_call or cond_5m_put
        breakdown["engulfing_1m_check"] = cond_1m_bull_engulf or cond_1m_bear_engulf
        breakdown["wick_check"] = wick_ok_call if c.is_bullish else wick_ok_put

        if cond_5m_call and cond_1m_bull_engulf and cond_1m_ema_call:
            if not wick_ok_call:
                return False, f"Upper wick rejection {upper_wick_ratio*100:.1f}% > 30% against CALL", breakdown

            confidence = min(96, int(75 + (body_ratio * 20) + (payout_pct / 20.0)))
            breakdown["confidence_score"] = confidence

            details = {
                "direction": "CALL",
                "pattern": "MTF_ENGULFING_1M",
                "expiry_minutes": 2,
                "confidence": confidence,
                "body_ratio": round(body_ratio, 3),
                "wick_ratio": round(upper_wick_ratio, 3),
                "ema_20_1m": round(ema_20_1m, 5),
                "ema_20_5m": round(ema_20_5m, 5),
                "payout_pct": payout_pct,
                "breakdown": breakdown
            }
            return True, "Bullish MTF Engulfing Breakout Confirmed", details

        if cond_5m_put and cond_1m_bear_engulf and cond_1m_ema_put:
            if not wick_ok_put:
                return False, f"Lower wick rejection {lower_wick_ratio*100:.1f}% > 30% against PUT", breakdown

            confidence = min(96, int(75 + (body_ratio * 20) + (payout_pct / 20.0)))
            breakdown["confidence_score"] = confidence

            details = {
                "direction": "PUT",
                "pattern": "MTF_ENGULFING_1M",
                "expiry_minutes": 2,
                "confidence": confidence,
                "body_ratio": round(body_ratio, 3),
                "wick_ratio": round(lower_wick_ratio, 3),
                "ema_20_1m": round(ema_20_1m, 5),
                "ema_20_5m": round(ema_20_5m, 5),
                "payout_pct": payout_pct,
                "breakdown": breakdown
            }
            return True, "Bearish MTF Engulfing Breakout Confirmed", details

        # Explain missing factor clearly
        reasons = []
        if not breakdown["trend_5m_check"]:
            reasons.append("5M EMA trend not aligned")
        if not breakdown["engulfing_1m_check"]:
            reasons.append("1M candle not engulfing prior high/low")
        if not breakdown["wick_check"]:
            reasons.append("Opposing wick rejection > 30%")

        reason_str = ", ".join(reasons) if reasons else "Confluence incomplete"
        return False, f"Waiting on setup: {reason_str}", breakdown
