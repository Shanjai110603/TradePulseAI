import random
from typing import Dict, Any, List, Optional
from app.engine.ai.base import AIProvider, AIAnalysisResult, PostSignalAIReview


class MockAIProvider(AIProvider):
    """
    High-quality deterministic/heuristic AI provider.
    Evaluates real technical indicators and market structure to return
    realistic structured ratings, biases, risks, and reasoning without API costs.
    """

    def get_provider_name(self) -> str:
        return "mock"

    async def analyze_signal(
        self,
        candidate_data: Dict[str, Any],
        technical_snapshot: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None
    ) -> AIAnalysisResult:
        direction = candidate_data.get("direction", "DOWN").upper()
        asset = candidate_data.get("asset_symbol", "EUR/USD")
        timeframe = candidate_data.get("timeframe", "1M")
        ref_price = candidate_data.get("reference_price", 1.08500)
        pattern_name = candidate_data.get("pattern_name", "Pattern Type 14")

        rsi = technical_snapshot.get("rsi", 50.0) or 50.0
        vol_ratio = technical_snapshot.get("volume_ratio", 1.0)
        trend = technical_snapshot.get("market_structure", {}).get("trend", "BEARISH")
        support_levels = technical_snapshot.get("support_levels", [])
        resistance_levels = technical_snapshot.get("resistance_levels", [])

        # Heuristic scoring calculation based on confluence
        score = 65

        # Factor in trend alignment
        if direction in ["DOWN", "SHORT", "SELL"] and trend in ["BEARISH", "STRONG_BEARISH"]:
            score += 15
            trend_assess = f"Firmly bearish multi-timeframe structure supporting short momentum on {timeframe}."
            bias = "BEARISH"
        elif direction in ["UP", "LONG", "BUY"] and trend in ["BULLISH", "STRONG_BULLISH"]:
            score += 15
            trend_assess = f"Strong bullish structure with price sustaining above short-term moving averages on {timeframe}."
            bias = "BULLISH"
        else:
            score -= 15
            trend_assess = f"Counter-trend / consolidation setup ({trend}) requiring strict risk boundaries."
            bias = "NEUTRAL" if direction not in ["UP", "DOWN"] else ("BEARISH" if direction == "DOWN" else "BULLISH")

        # Factor in momentum / RSI
        if direction in ["DOWN", "SHORT", "SELL"]:
            if rsi < 45:
                score += 10
                mom_assess = f"RSI at {rsi:.1f} confirms active downward selling pressure with room before extreme oversold territory."
            elif rsi > 60:
                score -= 15
                mom_assess = f"RSI at {rsi:.1f} indicates severe bullish counter-momentum against short trade."
            else:
                mom_assess = f"RSI at {rsi:.1f} indicates moderate selling momentum."
        else:
            if rsi > 55:
                score += 10
                mom_assess = f"RSI at {rsi:.1f} shows expanding buyer momentum."
            elif rsi < 40:
                score -= 15
                mom_assess = f"RSI at {rsi:.1f} indicates severe bearish counter-momentum against long trade."
            else:
                mom_assess = f"RSI at {rsi:.1f} indicates neutral upward pressure."

        # Factor in volume confirmation
        if vol_ratio >= 1.2:
            score += 10
            vol_assess = f"Volume is {(vol_ratio * 100):.0f}% of 20-period moving average, validating genuine breakdown participation."
        elif vol_ratio < 0.8:
            score -= 10
            vol_assess = f"Low volume ({(vol_ratio * 100):.0f}% of average), potential false move due to thin liquidity."
        else:
            vol_assess = f"Volume at {(vol_ratio * 100):.0f}% of average, moderate liquidity present."

        score = min(max(score, 15), 95)
        confidence = "HIGH" if score >= 80 else ("MODERATE" if score >= 60 else "LOW")

        struct_assess = f"Sequence completing {pattern_name} with confirmed boundary break at {ref_price}."
        if score >= 75:
            entry_qual = "Favorable technical confluence with immediate continuation potential."
            risk_assess = "Moderate — setup exhibits distinct invalidation levels."
        elif score >= 60:
            entry_qual = "Moderate confluence setup. Standard position sizing advised."
            risk_assess = "Moderate to High — partial confluence present."
        else:
            entry_qual = "Low confluence / counter-trend setup. High risk of false breakout."
            risk_assess = "HIGH RISK — Consider skipping or using minimal allocation."
        volatility = "High" if score < 60 else "Moderate"

        key_supports = support_levels[-2:] if support_levels else [round(ref_price * 0.999, 5)]
        key_resistances = resistance_levels[-2:] if resistance_levels else [round(ref_price * 1.001, 5)]

        reasoning = (
            f"The deterministic rule engine verified {pattern_name} conditions for {asset}. "
            f"Technical analysis confirms {trend_assess} Volume ratio of {vol_ratio:.2f} confirms breakdown participation. "
            f"The setup demonstrates high confluence with an AI alignment score of {score}/100."
        )

        risks = [
            f"Potential retest of broken level at {ref_price:.5f}",
            "Spike in spread during macroeconomic data release windows",
            "Wick rejection if higher timeframe support intervenes"
        ]

        invalidating_conditions = [
            f"Price retracing and closing above {key_resistances[0]:.5f}" if direction == "DOWN" else f"Price closing below {key_supports[0]:.5f}",
            "Sudden divergence on momentum oscillator within next 2 candles"
        ]

        return AIAnalysisResult(
            bias=bias,
            score=score,
            confidence=confidence,
            trend_assessment=trend_assess,
            momentum_assessment=mom_assess,
            volume_assessment=vol_assess,
            structure_assessment=struct_assess,
            entry_quality=entry_qual,
            risk_assessment=risk_assess,
            volatility=volatility,
            key_levels={
                "support": key_supports,
                "resistance": key_resistances
            },
            reasoning=reasoning,
            risks=risks,
            invalidating_conditions=invalidating_conditions,
            raw_response={"engine": "mock_quantitative_ai", "version": "1.0.0"}
        )

    async def post_signal_analysis(
        self,
        signal_data: Dict[str, Any],
        outcome_data: Dict[str, Any],
        historical_candles: List[Any]
    ) -> PostSignalAIReview:
        outcome = outcome_data.get("outcome", "WIN")
        pattern = signal_data.get("pattern_name", "Pattern Type 14")
        direction = signal_data.get("direction", "DOWN")

        if outcome == "WIN":
            return PostSignalAIReview(
                was_pattern_detection_correct=True,
                conditions_present=["Confirmed Support Break", "Volume Expansion", "Trend Continuity"],
                conditions_failed=[],
                ai_alignment_score=92,
                market_context_impact="Market followed structural momentum in direction of signal.",
                improvement_notes="Setup was executed with optimal timing and followed projected path."
            )
        else:
            return PostSignalAIReview(
                was_pattern_detection_correct=True,
                conditions_present=["Candle Sequence Match", "Initial Support Breakdown"],
                conditions_failed=["Momentum Follow-through", "False Break / Immediate Reversal"],
                ai_alignment_score=68,
                market_context_impact="Price encountered aggressive counter-liquidity leading to swift mean reversion.",
                improvement_notes="Consider adding stricter volume percentage threshold (>= 130%) or waiting for 1-candle confirmation pullback."
            )
