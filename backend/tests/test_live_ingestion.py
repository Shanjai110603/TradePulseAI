import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.engine.market_data.manager import market_data_manager


@pytest.mark.asyncio
async def test_live_candle_ingestion_and_retrieval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Ingest batch of real live candles
        payload = {
            "symbol": "EUR/USD (OTC)",
            "timeframe": "1M",
            "candles": [
                {"time": 1787900000, "open": 1.0850, "high": 1.0855, "low": 1.0848, "close": 1.0852, "volume": 1500},
                {"time": 1787900060, "open": 1.0852, "high": 1.0858, "low": 1.0850, "close": 1.0856, "volume": 1800},
                {"time": 1787900120, "open": 1.0856, "high": 1.0860, "low": 1.0853, "close": 1.0859, "volume": 2100},
                {"time": 1787900180, "open": 1.0859, "high": 1.0862, "low": 1.0855, "close": 1.0861, "volume": 1900},
                {"time": 1787900240, "open": 1.0861, "high": 1.0865, "low": 1.0858, "close": 1.0863, "volume": 2200},
                {"time": 1787900300, "open": 1.0863, "high": 1.0868, "low": 1.0860, "close": 1.0866, "volume": 2500},
            ]
        }
        res = await ac.post("/api/v1/markets/candles/ingest", json=payload, params={"api_key": settings.RELAY_API_KEY})
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["ingested_candles"] == 6

        # 2. Verify candles retrieved by market data manager
        provider = market_data_manager.get_provider("quotex")
        candles = await provider.get_candles("EUR/USD (OTC)", timeframe="1M", limit=10, strict_live_only=True)
        assert len(candles) == 6
        assert candles[-1].close == 1.0866
        assert candles[0].open == 1.0850


@pytest.mark.asyncio
async def test_live_candle_ingestion_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test missing fields with valid auth
        bad_payload = {"symbol": "EUR/USD (OTC)"}
        res = await ac.post("/api/v1/markets/candles/ingest", json=bad_payload, params={"api_key": settings.RELAY_API_KEY})
        assert res.status_code == 400
