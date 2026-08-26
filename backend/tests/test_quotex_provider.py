import pytest
from app.engine.market_data.quotex_provider import QuotexMarketDataProvider
from app.engine.market_data.manager import market_data_manager


@pytest.mark.asyncio
async def test_quotex_provider_assets():
    provider = QuotexMarketDataProvider()
    assets = await provider.get_assets("digital_options")
    assert len(assets) > 0
    symbols = [a["symbol"] for a in assets]
    assert "EUR/USD (OTC)" in symbols
    assert "BTC/USDT (OTC)" in symbols
    assert "EUR/USD" in symbols


@pytest.mark.asyncio
async def test_quotex_provider_candles():
    provider = QuotexMarketDataProvider()
    candles = await provider.get_candles("EUR/USD (OTC)", timeframe="1M", limit=50)
    assert len(candles) == 50
    assert candles[0].timestamp < candles[-1].timestamp
    for c in candles:
        assert c.high >= c.low
        assert c.high >= c.open
        assert c.high >= c.close
        assert c.low <= c.open
        assert c.low <= c.close


@pytest.mark.asyncio
async def test_quotex_provider_current_price():
    provider = QuotexMarketDataProvider()
    price = await provider.get_current_price("EUR/USD (OTC)")
    assert price > 0.5 and price < 2.0


@pytest.mark.asyncio
async def test_market_data_manager_quotex():
    provider = market_data_manager.get_provider("quotex")
    assert isinstance(provider, QuotexMarketDataProvider)
    # is_live() returns True only when QUOTEX_SESSION_TOKEN is set in env
    # In test environment without token, it should return False (simulation mode)
    from app.core.config import settings
    expected_live = bool(getattr(settings, "QUOTEX_SESSION_TOKEN", "") and
                         len(getattr(settings, "QUOTEX_SESSION_TOKEN", "")) > 10)
    assert provider.is_live() == expected_live
