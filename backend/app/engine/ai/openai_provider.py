import json
import httpx
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.engine.ai.base import AIProvider, AIAnalysisResult, PostSignalAIReview


class OpenAIProvider(AIProvider):
    """OpenAI API Provider with strict JSON schema output enforcement"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.AI_API_KEY
        self.model = model or settings.AI_MODEL or "gpt-4o-mini"
        self.base_url = "https://api.openai.com/v1"

    def get_provider_name(self) -> str:
        return "openai"

    async def analyze_signal(
        self,
        candidate_data: Dict[str, Any],
        technical_snapshot: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None
    ) -> AIAnalysisResult:
        if not self.api_key:
            raise ValueError("OpenAI API Key is not configured")

        prompt = f"""
You are a quantitative senior market analyst. Analyze this verified deterministic signal candidate:
Candidate: {json.dumps(candidate_data, default=str)}
Technicals: {json.dumps(technical_snapshot, default=str)}
Market Context: {json.dumps(market_context or {}, default=str)}

Return a strict JSON object with these exact fields:
- bias: "BULLISH", "BEARISH", or "NEUTRAL"
- score: integer from 0 to 100
- confidence: "LOW", "MODERATE", or "HIGH"
- trend_assessment: short string
- momentum_assessment: short string
- volume_assessment: short string
- structure_assessment: short string
- entry_quality: short string
- risk_assessment: short string
- volatility: string
- key_levels: object with "support": [floats], "resistance": [floats]
- reasoning: detailed markdown paragraph explaining rationale
- risks: array of strings
- invalidating_conditions: array of strings
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a quantitative market research analyst. Respond in strict JSON only."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": settings.AI_TEMPERATURE
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            parsed["raw_response"] = {"model": self.model, "usage": data.get("usage", {})}
            return AIAnalysisResult(**parsed)

    async def post_signal_analysis(
        self,
        signal_data: Dict[str, Any],
        outcome_data: Dict[str, Any],
        historical_candles: List[Any]
    ) -> PostSignalAIReview:
        if not self.api_key:
            raise ValueError("OpenAI API Key is not configured")

        prompt = f"""
Analyze the outcome of this completed trade signal:
Signal: {json.dumps(signal_data, default=str)}
Outcome: {json.dumps(outcome_data, default=str)}

Provide a strict JSON object:
- was_pattern_detection_correct: boolean
- conditions_present: array of strings
- conditions_failed: array of strings
- ai_alignment_score: integer 0-100
- market_context_impact: string
- improvement_notes: string
"""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a quantitative trade debrief analyst. Respond in strict JSON only."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
            return PostSignalAIReview(**parsed)
