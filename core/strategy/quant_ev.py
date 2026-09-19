"""
Quant Expected Value (EV) & Positive-Edge Mathematical Gating Filter
====================================================================
Evaluates live broker payouts against historical/modeled win rates to enforce
positive mathematical expectancy (EV > 0) before any signal can be fired.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("TradePulse.QuantEV")


class QuantEVFilter:
    """Calculates mathematical expected value and gates signals based on positive trader edge."""

    def __init__(self):
        self.enabled: bool = True
        self.require_positive_ev: bool = True
        self.min_confidence: float = 55.0  # Minimum confidence threshold %
        self.engine_mode: str = "quant"   # 'quant' (strict EV), 'confluence' (voting), 'learned' (ML scoring)
        self.min_payout_clamp: float = 50.0

    def configure(
        self,
        enabled: Optional[bool] = None,
        require_positive_ev: Optional[bool] = None,
        min_confidence: Optional[float] = None,
        engine_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dynamically updates Quant EV preferences."""
        if enabled is not None:
            self.enabled = bool(enabled)
        if require_positive_ev is not None:
            self.require_positive_ev = bool(require_positive_ev)
        if min_confidence is not None:
            self.min_confidence = max(50.0, min(95.0, float(min_confidence)))
        if engine_mode is not None and engine_mode.lower() in ("quant", "confluence", "learned"):
            self.engine_mode = engine_mode.lower()

        logger.info(
            f"[QUANT EV] Config updated: enabled={self.enabled}, "
            f"positive_ev_only={self.require_positive_ev}, "
            f"min_confidence={self.min_confidence}%, mode={self.engine_mode}"
        )
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Returns current configuration dictionary."""
        return {
            "enabled": self.enabled,
            "require_positive_ev": self.require_positive_ev,
            "min_confidence": self.min_confidence,
            "engine_mode": self.engine_mode
        }

    @staticmethod
    def calculate_breakeven_rate(payout_pct: float) -> float:
        """
        Calculates minimum win rate required to break even for a given broker payout percentage.
        Formula: 100 / (100 + payout)
        Example: 85% payout -> 100 / 185 = 54.05%
        """
        clamped_payout = max(10.0, float(payout_pct))
        return round(100.0 / (100.0 + clamped_payout) * 100.0, 2)

    @staticmethod
    def calculate_expected_value(win_rate_pct: float, payout_pct: float, stake: float = 1.0) -> float:
        """
        Calculates mathematical Expected Value (EV) per trade for given win rate and payout.
        Formula: EV = (P_win * Profit) - (P_loss * Stake)
        """
        p_win = max(0.0, min(100.0, float(win_rate_pct))) / 100.0
        p_loss = 1.0 - p_win
        profit = stake * (float(payout_pct) / 100.0)
        loss = stake * 1.0
        return round((p_win * profit) - (p_loss * loss), 4)

    def evaluate_edge(
        self,
        symbol: str,
        live_payout: float,
        strategy_win_rate: Optional[float] = None,
        confidence_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates whether a candidate signal has positive expected value (EV > 0)
        and meets the active engine thresholds.
        """
        if not self.enabled:
            return {
                "passed": True,
                "ev": 0.0,
                "edge_pct": 0.0,
                "breakeven_win_rate": self.calculate_breakeven_rate(live_payout or 85.0),
                "measured_win_rate": strategy_win_rate or 60.0,
                "reason": "Quant EV filter disabled"
            }

        payout = float(live_payout or 85.0)
        breakeven_rate = self.calculate_breakeven_rate(payout)

        # Determine effective win probability (defaults to confidence or conservative 60%)
        if strategy_win_rate and strategy_win_rate > 0:
            effective_rate = float(strategy_win_rate)
        elif confidence_score and confidence_score > 0:
            effective_rate = float(confidence_score)
        else:
            effective_rate = 60.0

        ev = self.calculate_expected_value(effective_rate, payout, stake=1.0)
        edge_pct = round(effective_rate - breakeven_rate, 2)

        # Mode-specific gating
        if self.engine_mode == "confluence":
            # Confluence mode: fast voting based on minimum confidence
            passed = effective_rate >= self.min_confidence
            reason = (
                f"Confidence {effective_rate:.1f}% >= min {self.min_confidence:.1f}%"
                if passed
                else f"Confidence {effective_rate:.1f}% below min {self.min_confidence:.1f}%"
            )
        else:
            # Quant mode (default) & Learned mode: strict Expected Value gating
            meets_confidence = effective_rate >= self.min_confidence
            is_positive_ev = ev > 0 if self.require_positive_ev else True

            passed = meets_confidence and is_positive_ev
            if not meets_confidence:
                reason = f"Win probability ({effective_rate:.1f}%) below minimum confidence ({self.min_confidence:.1f}%)"
            elif not is_positive_ev:
                reason = f"Negative expected value: EV={ev:+.3f} (Rate {effective_rate:.1f}% < Breakeven {breakeven_rate:.1f}% for {payout:.0f}% payout)"
            else:
                reason = f"Positive mathematical edge (+{edge_pct:.1f}% edge, EV={ev:+.3f})"

        return {
            "passed": passed,
            "ev": ev,
            "edge_pct": edge_pct,
            "breakeven_win_rate": breakeven_rate,
            "measured_win_rate": effective_rate,
            "reason": reason
        }
