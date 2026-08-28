from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class Candle(BaseModel):
    timestamp: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        return abs(self.close - self.open) <= (self.high - self.low) * 0.05

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


class MarketDataProvider(ABC):
    """Abstract base class for all market data providers"""

    @abstractmethod
    async def get_assets(self, market_id: str) -> List[Dict[str, Any]]:
        """Returns list of supported assets for a market"""
        pass

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1M",
        limit: int = 100,
        end_time: Optional[datetime] = None,
        strict_live_only: bool = True
    ) -> List[Candle]:
        """Returns historical OHLCV candles sorted chronologically (oldest to newest)"""
        pass

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        """Returns latest reference/spot price for an asset"""
        pass

    @abstractmethod
    def get_supported_timeframes(self) -> List[str]:
        """Returns list of timeframe strings supported by provider"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns provider name identifier"""
        pass

    @abstractmethod
    def is_live(self) -> bool:
        """Returns True if provider supplies real-time live data, False if mock/delayed/historical"""
        pass
