# AI Provider Abstraction & Quantitative Scoring

## Overview

TradePulse AI utilizes an abstract `AIProvider` interface. AI analysis occurs **after** deterministic pattern matching has identified a candidate setup.

## Provider Abstraction

```python
class AIProvider(ABC):
    @abstractmethod
    async def analyze_signal(self, candidate_data, technical_snapshot, market_context) -> AIAnalysisResult:
        pass

    @abstractmethod
    async def post_signal_analysis(self, signal_data, outcome_data, historical_candles) -> PostSignalAIReview:
        pass
```

### Supported Providers

1. **`mock`**: Deterministic quantitative heuristic engine that calculates realistic scores and reasoning from real indicators without API costs or external keys.
2. **`openai`**: Integrates with GPT-4o / GPT-4o-mini using JSON Schema enforcement.
3. **`anthropic` & `gemini`**: Pluggable adapters via standard REST/SDK endpoints.

## AI Structured Output Schema

All AI responses are validated through Pydantic schemas:
- `bias`: `"BULLISH" | "BEARISH" | "NEUTRAL"`
- `score`: `0 - 100`
- `confidence`: `"LOW" | "MODERATE" | "HIGH"`
- `trend_assessment`: String
- `momentum_assessment`: String
- `volume_assessment`: String
- `structure_assessment`: String
- `entry_quality`: String
- `risk_assessment`: String
- `volatility`: String
- `key_levels`: `{"support": [...], "resistance": [...]}`
- `reasoning`: Comprehensive analysis paragraph
- `risks`: Array of risk factors
- `invalidating_conditions`: Array of conditions that invalidate the setup
