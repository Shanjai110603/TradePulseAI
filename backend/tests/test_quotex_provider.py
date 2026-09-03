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
    candles = await provider.get_candles("EUR/USD (OTC)", timeframe="1M", limit=50, strict_live_only=False)
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
    # Without live data, honestly returns None rather than fabricating numbers
    price = await provider.get_current_price("EUR/USD (OTC)")
    assert price is None

    # After genuine candles are ingested via relay, returns genuine live price
    provider.ingest_candles("EUR/USD (OTC)", "1M", [
        {"time": 1787900000, "open": 1.0850, "high": 1.0855, "low": 1.0848, "close": 1.0852}
    ])
    live_price = await provider.get_current_price("EUR/USD (OTC)")
    assert live_price == 1.0852
    assert provider.is_live() is True


@pytest.mark.asyncio
async def test_market_data_manager_quotex():
    provider = market_data_manager.get_provider("quotex")
    assert isinstance(provider, QuotexMarketDataProvider)
    # is_live() reflects recent successful fetch/ingest freshness
    assert isinstance(provider.is_live(), bool)
