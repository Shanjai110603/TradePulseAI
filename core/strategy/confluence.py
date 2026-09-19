"""
TradePulse Confluence & Explainability Engine
Calculates transparent, deterministic Setup Quality Scores (75–96%) based on
user rule criteria, solid body ratios, and live broker payouts (no fake AI).
"""
from typing import Any, Dict, Tuple
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
        rule_details: Dict[str, Any]
    ) -> Tuple[int, str, Dict[str, Any]]:
        """
        Calculates verified Setup Quality Score and qualitative tier:
        Base: 72
        + Body ratio bonus (up to +18 points for strong Marubozu bars)
        + Payout bonus (up to +5.0 points for 90%+ payouts)
        + Small wick bonus (up to +4 points for clean directional push)
        Clamped to [75, 96]
        """
        body_ratio = candle.body_ratio
        wick_ratio = candle.opposing_wick_ratio

        # Points
        body_pts = min(18.0, body_ratio * 20.0)
        payout_pts = min(5.0, payout_pct / 20.0)
        wick_pts = 4.0 if wick_ratio <= 0.20 else (2.0 if wick_ratio <= 0.30 else 0.0)

        raw_score = 72.0 + body_pts + payout_pts + wick_pts
        final_score = int(min(96, max(75, round(raw_score))))
        tier = cls.get_tier(final_score)

        audit = {
            "score": final_score,
            "tier": tier,
            "body_ratio": round(body_ratio * 100, 1),
            "opposing_wick_ratio": round(wick_ratio * 100, 1),
            "live_payout": payout_pct,
            "rule_details": rule_details
        }
        return final_score, tier, audit

    @classmethod
    def calculate_confidence(
        cls,
        candle: Candle,
        payout_pct: float,
        rule_details: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any]]:
        """Backward-compatible wrapper returning (score, audit)."""
        score, _, audit = cls.calculate_setup_quality_score(candle, payout_pct, rule_details)
        return score, audit
