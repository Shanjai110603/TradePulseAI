import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.engine.ai.base import AIProvider, AIAnalysisResult, PostSignalAIReview
from app.engine.ai.mock_ai import MockAIProvider

logger = logging.getLogger(__name__)


class OpenRouterAIProvider(AIProvider):
    """
    OpenRouter API Provider supporting top LLMs (GPT-4o, Claude 3.5, DeepSeek R1, Llama 3)
    via OpenAI-compatible API gateway with automatic fallback to heuristic analysis.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.AI_API_KEY or settings.OPENROUTER_API_KEY
        self.model = model or settings.AI_MODEL or "openai/gpt-4o-mini"
        self.base_url = "https://openrouter.ai/api/v1"
        self._fallback = MockAIProvider()

    def get_provider_name(self) -> str:
        return "openrouter"

    async def analyze_signal(
        self,
        candidate_data: Dict[str, Any],
        technical_snapshot: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None
    ) -> AIAnalysisResult:
        if not self.api_key:
            logger.info("No OpenRouter API key found; using quantitative heuristic AI provider.")
            return await self._fallback.analyze_signal(candidate_data, technical_snapshot, market_context)

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
            "HTTP-Referer": "https://tradepulse.ai",
            "X-Title": "TradePulse AI Market Station",
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

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    parsed["raw_response"] = {"provider": "openrouter", "model": self.model, "usage": data.get("usage", {})}
                    return AIAnalysisResult(**parsed)
                else:
                    logger.warning(f"OpenRouter API returned {resp.status_code}: {resp.text}. Falling back to heuristic AI.")
        except Exception as e:
            logger.error(f"OpenRouter call failed ({e}). Falling back to heuristic AI engine.")

        return await self._fallback.analyze_signal(candidate_data, technical_snapshot, market_context)

    async def post_signal_analysis(
        self,
        signal_data: Dict[str, Any],
        outcome_data: Dict[str, Any],
        historical_candles: List[Any]
    ) -> PostSignalAIReview:
        if not self.api_key:
            return await self._fallback.post_signal_analysis(signal_data, outcome_data, historical_candles)

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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://tradepulse.ai",
            "X-Title": "TradePulse AI Market Station",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a quantitative trade debrief analyst. Respond in strict JSON only."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
                    return PostSignalAIReview(**parsed)
        except Exception as e:
            logger.error(f"OpenRouter post-signal review failed: {e}")

        return await self._fallback.post_signal_analysis(signal_data, outcome_data, historical_candles)
