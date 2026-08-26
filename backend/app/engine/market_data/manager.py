from typing import Dict, Optional, List, Any
from app.core.config import settings
from app.engine.market_data.base import MarketDataProvider
from app.engine.market_data.mock_provider import MockDataProvider
from app.engine.market_data.binance_provider import BinanceDataProvider
from app.engine.market_data.quotex_provider import QuotexMarketDataProvider


class MarketDataManager:
    """
    Registry and factory for market data providers.
    Supports seamless switching between Mock, Binance, Quotex, and future data providers.
    """

    def __init__(self):
        self._providers: Dict[str, MarketDataProvider] = {
            "mock": MockDataProvider(),
            "binance": BinanceDataProvider(),
            "quotex": QuotexMarketDataProvider(),
        }
        self._default_provider_name = settings.MARKET_DATA_PROVIDER

    def register_provider(self, name: str, provider: MarketDataProvider):
        self._providers[name] = provider

    def get_provider(self, provider_name: Optional[str] = None) -> MarketDataProvider:
        name = provider_name or self._default_provider_name
        provider = self._providers.get(name)
        if not provider:
            # Fallback to mock provider
            return self._providers["mock"]
        return provider

    def get_mock_provider(self) -> MockDataProvider:
        return self._providers["mock"]  # type: ignore

    def list_providers(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": name,
                "is_live": prov.is_live(),
                "timeframes": prov.get_supported_timeframes()
            }
            for name, prov in self._providers.items()
        ]


# Singleton instance
market_data_manager = MarketDataManager()
