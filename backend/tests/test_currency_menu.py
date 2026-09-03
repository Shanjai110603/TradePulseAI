import pytest
from app.telegram.formatter import TelegramMessageFormatter


def test_currency_categories_menu_formatting():
    text, kb = TelegramMessageFormatter.format_currency_categories_menu()
    assert "QUOTEX LIVE CURRENCY & TRADE DIRECTORY" in text
    assert "Forex OTC" in text
    assert "Crypto OTC" in text
    assert "Commodities" in text
    assert "Live Forex" in text
    assert len(kb) >= 3


def test_currency_list_pagination():
    text, kb = TelegramMessageFormatter.format_currency_list("forex_otc", page=0)
    assert "FOREX OTC PAIRS" in text
    assert "EUR/USD (OTC)" in text
    assert "USD/BRL (OTC)" in text
    assert len(kb) >= 3


@pytest.mark.asyncio
async def test_currency_monitor_card_rendering():
    from app.engine.market_data.manager import market_data_manager
    provider = market_data_manager.get_provider("quotex")
    
    current_price = await provider.get_current_price("USD/BRL (OTC)")
    candles = await provider.get_candles("USD/BRL (OTC)", timeframe="1M", limit=25, strict_live_only=False)
    latest = candles[-1].model_dump() if candles else None
    tech_snapshot = provider.compute_technical_snapshot(candles, current_price)

    text, kb = TelegramMessageFormatter.format_currency_monitor_card(
        symbol_name="USD/BRL (OTC)",
        symbol_code="USDBRL_otc",
        current_price=current_price,
        payout_pct="95%",
        candles_count=len(candles),
        latest_candle=latest,
        tech_snapshot=tech_snapshot
    )
    assert "LIVE ASSET MONITOR: USD/BRL (OTC)" in text
    if current_price is not None:
        assert f"{current_price:.5f}" in text
        assert "95%" in text
        assert any("Refresh Live Price" in b["text"] for row in kb for b in row)
        assert any("Generate 1M Chart" in b["text"] for row in kb for b in row)
        assert any("Set Signal Alert" in b["text"] for row in kb for b in row)
    else:
        assert "No live data right now" in text
        assert any("Retry" in b["text"] for row in kb for b in row)


@pytest.mark.asyncio
async def test_callback_query_currency_selection_pipeline():
    from app.telegram.handlers import TelegramUpdateHandler
    from app.core.database import AsyncSessionLocal

    cb_payload = {
        "id": "test_cb_12345",
        "from": {"id": 123456, "first_name": "Trader"},
        "message": {
            "message_id": 9999,
            "chat": {"id": 123456, "type": "private"},
            "text": "Existing menu"
        },
        "data": "curr_sel:USDBRL_otc"
    }

    async with AsyncSessionLocal() as db:
        # Must execute cleanly without throwing AttributeError on compute_technical_snapshot
        await TelegramUpdateHandler._handle_callback_query(cb_payload, db)
