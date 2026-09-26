"""
TradePulse Confluence & Explainability Engine
Calculates transparent, deterministic Setup Quality Scores (75–96%) based on
multi-factor confluence: candle anatomy, indicator alignment, formation confirmation,
structural trend, live broker payouts, and multi-timeframe agreement.
Inspired by StrategyQuant robustness scoring and Backtrader analyzer metrics.
"""
from typing import Any, Dict, Optional, Tuple
from core.models.candle import Candle


class ConfluenceEngine:
    """Calculates quantitative Setup Quality Scores and explainability audit trails."""

    @staticmethod
    def get_tier(score: int) -> str:
        """Categorizes numerical setup score into qualitative tier."""
        if score >= 90:
            return "PREMIUM"
        elif score >= 80:
            return "STRONG"
        return "STANDARD"

    @classmethod
    def calculate_setup_quality_score(
        cls,
        candle: Candle,
        payout_pct: float,
        rule_details: Dict[str, Any],
        technical_snapshot: Optional[Dict[str, Any]] = None,
        direction: str = "CALL"
    ) -> Tuple[int, str, Dict[str, Any]]:
        """
        Calculates verified Setup Quality Score using multi-factor confluence:
        
        Base: 60
        + Body ratio bonus (up to +10 points for strong Marubozu bars)
        + Payout bonus (up to +4 points for 90%+ payouts)
        + Small wick bonus (up to +3 points for clean directional push)
        + Indicator alignment bonus (up to +8 points)
        + Formation confirmation bonus (up to +6 points)
        + Structural trend bonus (up to +5 points)
        + Volume confirmation bonus (up to +3 points)
        Clamped to [75, 96]
        """
        body_ratio = candle.body_ratio
        wick_ratio = candle.opposing_wick_ratio

        # 1. Candle anatomy points
        body_pts = min(10.0, body_ratio * 12.5)
        wick_pts = 3.0 if wick_ratio <= 0.15 else (2.0 if wick_ratio <= 0.25 else (1.0 if wick_ratio <= 0.35 else 0.0))
        payout_pts = min(4.0, payout_pct / 22.5)

        # 2. Indicator alignment scoring (if snapshot available)
        indicator_pts = 0.0
        formation_pts = 0.0
        structure_pts = 0.0
        volume_pts = 0.0
        indicator_factors = []

        if technical_snapshot:
            dir_upper = direction.upper()
            is_call = dir_upper in ("CALL", "BUY", "UP")

            # RSI alignment
            rsi = technical_snapshot.get("rsi")
            if rsi is not None:
                if is_call and rsi < 40:
                    indicator_pts += 2.0
                    indicator_factors.append("RSI_OVERSOLD")
                elif not is_call and rsi > 60:
                    indicator_pts += 2.0
                    indicator_factors.append("RSI_OVERBOUGHT")

            # MACD histogram alignment
            macd = technical_snapshot.get("macd")
            if isinstance(macd, dict):
                hist = macd.get("histogram", 0.0)
                hist_inc = macd.get("hist_increasing", False)
                if is_call and hist > 0 and hist_inc:
                    indicator_pts += 2.0
                    indicator_factors.append("MACD_BULLISH_EXPANDING")
                elif not is_call and hist < 0 and macd.get("hist_decreasing", False):
                    indicator_pts += 2.0
                    indicator_factors.append("MACD_BEARISH_EXPANDING")

            # Supertrend alignment
            st = technical_snapshot.get("supertrend")
            if isinstance(st, dict):
                st_trend = st.get("trend", "")
                if (is_call and st_trend == "BULLISH") or (not is_call and st_trend == "BEARISH"):
                    indicator_pts += 2.0
                    indicator_factors.append(f"SUPERTREND_{st_trend}")

            # EMA trend alignment
            ema_fast = technical_snapshot.get("ema_fast")
            ema_slow = technical_snapshot.get("ema_slow")
            if ema_fast and ema_slow:
                if (is_call and ema_fast > ema_slow) or (not is_call and ema_fast < ema_slow):
                    indicator_pts += 2.0
                    indicator_factors.append("EMA_TREND_ALIGNED")

            indicator_pts = min(8.0, indicator_pts)

            # 3. Formation confirmation scoring
            formations = technical_snapshot.get("formations")
            if isinstance(formations, dict):
                detected = formations.get("detected_patterns", [])
                if is_call:
                    bullish_patterns = [p for p in detected if "BULLISH" in p or p in ("MORNING_STAR", "THREE_WHITE_SOLDIERS", "TWEEZER_BOTTOM")]
                    if bullish_patterns:
                        formation_pts = min(6.0, len(bullish_patterns) * 3.0)
                        indicator_factors.extend(bullish_patterns)
                else:
                    bearish_patterns = [p for p in detected if "BEARISH" in p or p in ("EVENING_STAR", "THREE_BLACK_CROWS", "TWEEZER_TOP")]
                    if bearish_patterns:
                        formation_pts = min(6.0, len(bearish_patterns) * 3.0)
                        indicator_factors.extend(bearish_patterns)

            # 4. Market structure scoring
            smc = technical_snapshot.get("smc_structure")
            if isinstance(smc, dict):
                struct_trend = smc.get("structure_trend", "NEUTRAL")
                if (is_call and struct_trend == "BULLISH") or (not is_call and struct_trend == "BEARISH"):
                    structure_pts += 3.0
                    indicator_factors.append(f"STRUCTURE_{struct_trend}")
                if (is_call and smc.get("bos_bullish")) or (not is_call and smc.get("bos_bearish")):
                    structure_pts += 2.0
                    indicator_factors.append("BOS_CONFIRMED")
                structure_pts = min(5.0, structure_pts)

            # 5. Volume confirmation
            vol_ratio = technical_snapshot.get("volume_ratio", 1.0)
            if vol_ratio >= 1.5:
                volume_pts = 3.0
                indicator_factors.append("HIGH_VOLUME")
            elif vol_ratio >= 1.2:
                volume_pts = 1.5
                indicator_factors.append("ABOVE_AVG_VOLUME")

        raw_score = 60.0 + body_pts + payout_pts + wick_pts + indicator_pts + formation_pts + structure_pts + volume_pts
        final_score = int(min(96, max(75, round(raw_score))))
        tier = cls.get_tier(final_score)

        audit = {
            "score": final_score,
            "tier": tier,
            "body_ratio": round(body_ratio * 100, 1),
            "opposing_wick_ratio": round(wick_ratio * 100, 1),
            "live_payout": payout_pct,
            "body_pts": round(body_pts, 1),
            "wick_pts": round(wick_pts, 1),
            "payout_pts": round(payout_pts, 1),
            "indicator_alignment_pts": round(indicator_pts, 1),
            "formation_confirmation_pts": round(formation_pts, 1),
            "structure_pts": round(structure_pts, 1),
            "volume_pts": round(volume_pts, 1),
            "confluence_factors": indicator_factors,
            "rule_details": rule_details
        }
        return final_score, tier, audit

    @classmethod
    def calculate_confidence(
        cls,
        candle: Candle,
        payout_pct: float,
        rule_details: Dict[str, Any],
        technical_snapshot: Optional[Dict[str, Any]] = None,
        direction: str = "CALL"
    ) -> Tuple[int, Dict[str, Any]]:
        """Backward-compatible wrapper returning (score, audit)."""
        score, _, audit = cls.calculate_setup_quality_score(candle, payout_pct, rule_details, technical_snapshot, direction)
        return score, audit
