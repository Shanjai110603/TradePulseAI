import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from app.engine.market_data.base import Candle, MarketDataProvider
from app.engine.indicators.engine import TechnicalIndicatorEngine
from app.engine.rules.engine import PatternRuleEngine
from app.engine.ai.base import AIProvider, AIAnalysisResult
from app.engine.ai.manager import ai_manager
from app.engine.filters.engine import UserFilterEngine


class SignalEvaluationPipeline:
    """
    End-to-end signal evaluation engine:
    Market Data -> Deterministic Rules -> Technical Snapshot -> AI Analysis -> User Filters -> Validated Signal.
    """

    @classmethod
    async def evaluate_candidate(
        cls,
        pattern_dict: Dict[str, Any],
        candles: List[Candle],
        multi_timeframe_candles: Optional[Dict[str, List[Candle]]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        ai_provider: Optional[AIProvider] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], str, Dict[str, Any]]:
        """
        Evaluates a single pattern against candle history.
        Returns:
            (is_signal_created: bool, signal_payload: Optional[dict], decision_reason: str, audit_trail: dict)
        """
        audit_trail: Dict[str, Any] = {}

        # 1. Deterministic Rule Engine
        rule_result = PatternRuleEngine.evaluate_pattern(pattern_dict, candles, multi_timeframe_candles)
        audit_trail["rule_evaluation"] = rule_result
        
        if not rule_result.get("matched", False):
            return False, None, rule_result.get("reason", "Deterministic rules not satisfied"), audit_trail

        technical_snapshot = rule_result.get("technical_snapshot", {})
        reference_price = rule_result.get("reference_price", candles[-1].close)
        direction = rule_result.get("direction", pattern_dict.get("direction", "DOWN")).upper()
        asset_symbol = pattern_dict.get("asset_symbol", "EUR/USD")
        timeframe = pattern_dict.get("timeframe", "1M")
        pattern_name = pattern_dict.get("name", "Custom Pattern")

        candidate_data = {
            "pattern_id": pattern_dict.get("id"),
            "pattern_name": pattern_name,
            "pattern_version": pattern_dict.get("current_version", 1),
            "market_id": pattern_dict.get("market_id", "digital_options"),
            "asset_symbol": asset_symbol,
            "direction": direction,
            "timeframe": timeframe,
            "reference_price": reference_price,
            "entry_time": datetime.now(timezone.utc),
        }

        # 2. AI Analysis Layer
        active_ai = ai_provider or ai_manager.get_provider()
        ai_analysis: AIAnalysisResult = await active_ai.analyze_signal(
            candidate_data=candidate_data,
            technical_snapshot=technical_snapshot,
            market_context={"market_id": pattern_dict.get("market_id")}
        )
        audit_trail["ai_analysis"] = ai_analysis.model_dump()

        # 3. User Filter Engine
        filter_passed, filter_reason, filter_audit = UserFilterEngine.evaluate_filters(
            candidate_data=candidate_data,
            ai_analysis=ai_analysis,
            pattern_config=pattern_dict,
            user_preferences=user_preferences
        )
        audit_trail["filters"] = filter_audit

        if not filter_passed:
            return False, None, f"Filter rejected: {filter_reason}", audit_trail

        # 4. Signal Creation Payload Construction
        # Determine targets / expiry
        market_id = pattern_dict.get("market_id", "digital_options")
        target_cfg = pattern_dict.get("target_config", {})
        entry_time = datetime.now(timezone.utc)

        duration_minutes = rule_result.get("expiry_minutes") or int(target_cfg.get("duration_minutes", 1))
        if duration_minutes <= 0:
            duration_minutes = 1
        expiry_time = entry_time + timedelta(minutes=duration_minutes)

        # Standard market SL/TP targets
        stop_loss = None
        tp1 = None
        tp2 = None
        tp3 = None
        rr = target_cfg.get("risk_reward_ratio", 2.0)

        atr_val = technical_snapshot.get("atr") or (reference_price * 0.001)
        if market_id != "digital_options":
            if direction in ["UP", "LONG", "BUY"]:
                stop_loss = round(reference_price - (atr_val * 1.5), 5)
                risk = reference_price - stop_loss
                tp1 = round(reference_price + risk, 5)
                tp2 = round(reference_price + (risk * rr), 5)
                tp3 = round(reference_price + (risk * rr * 1.5), 5)
            else:
                stop_loss = round(reference_price + (atr_val * 1.5), 5)
                risk = stop_loss - reference_price
                tp1 = round(reference_price - risk, 5)
                tp2 = round(reference_price - (risk * rr), 5)
                tp3 = round(reference_price - (risk * rr * 1.5), 5)

        strength = "HIGH" if ai_analysis.score >= 85 else ("MODERATE" if ai_analysis.score >= 75 else "LOW")

        signal_payload = {
            "id": str(uuid.uuid4()),
            "pattern_id": pattern_dict.get("id"),
            "pattern_version": pattern_dict.get("current_version", 1),
            "pattern_name": pattern_name,
            "market_id": market_id,
            "asset_symbol": asset_symbol,
            "direction": direction,
            "timeframe": timeframe,
            "reference_price": reference_price,
            "support_level": rule_result.get("support_level") or technical_snapshot.get("support_levels", [None])[-1],
            "resistance_level": rule_result.get("resistance_level") or technical_snapshot.get("resistance_levels", [None])[-1],
            "entry_time": entry_time,
            "expiry_time": expiry_time,
            "duration_minutes": duration_minutes,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "risk_reward_ratio": rr if market_id != "digital_options" else None,
            "signal_strength": strength,
            "ai_score": ai_analysis.score,
            "ai_confidence": ai_analysis.confidence,
            "status": "ACTIVE",
            "technical_snapshot": technical_snapshot,
            "ai_analysis": ai_analysis.model_dump(),
            "raw_trigger_candles": [c.model_dump() for c in candles[-10:]]
        }

        # Render live trade candlestick chart snapshot
        try:
            from app.engine.charts.chart_generator import TradeChartGenerator
            chart_path = TradeChartGenerator.generate_chart(candles=candles, signal_data=signal_payload)
            signal_payload["image_path"] = chart_path
        except Exception as chart_err:
            pass

        return True, signal_payload, "Signal validated and generated", audit_trail
