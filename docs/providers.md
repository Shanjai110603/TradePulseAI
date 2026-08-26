# Data & AI Provider Abstraction

## Overview

TradePulse AI is designed around decoupled interfaces for both **Market Data** and **AI Analysis**. This ensures that switching or adding new data feeds (crypto, forex, stock brokers, synthetic simulators) or AI models (OpenAI, Anthropic, Gemini, local models) never requires rewriting strategy rules or pattern evaluators.

## 1. Market Data Providers (`app.engine.market_data`)

### Interface
```python
class MarketDataProvider(ABC):
    @abstractmethod
    async def get_assets(self, market_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def get_candles(self, symbol: str, timeframe: str, limit: int, end_time: Optional[datetime]) -> List[Candle]: ...

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float: ...

    @abstractmethod
    def get_supported_timeframes(self) -> List[str]: ...

    @abstractmethod
    def is_live(self) -> bool: ...
```

### Implementing a New Provider
To add a new market data provider (e.g. `AlpacaDataProvider` or `YahooFinanceProvider`):
1. Create `backend/app/engine/market_data/your_provider.py` subclassing `MarketDataProvider`.
2. Implement `get_assets`, `get_candles`, `get_current_price`, and `is_live`.
3. Register the provider in `backend/app/engine/market_data/manager.py`.

---

## 2. AI Analysis Providers (`app.engine.ai`)

### Interface
```python
class AIProvider(ABC):
    @abstractmethod
    async def analyze_signal(self, candidate_data, technical_snapshot, market_context) -> AIAnalysisResult: ...

    @abstractmethod
    async def post_signal_analysis(self, signal_data, outcome_data, historical_candles) -> PostSignalAIReview: ...
```

### Implementing a New AI Provider
To add a new AI provider (e.g. `AnthropicClaudeProvider` or `LocalOllamaProvider`):
1. Create `backend/app/engine/ai/your_provider.py` subclassing `AIProvider`.
2. Ensure the response is validated through `AIAnalysisResult` and `PostSignalAIReview` Pydantic models.
3. Register the provider in `backend/app/engine/ai/manager.py`.
