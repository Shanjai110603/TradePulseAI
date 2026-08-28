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


def test_currency_monitor_card_rendering():
    text, kb = TelegramMessageFormatter.format_currency_monitor_card(
        symbol_name="USD/BRL (OTC)",
        symbol_code="USDBRL_otc",
        current_price=0.20184,
        payout_pct="95%",
        candles_count=30,
        latest_candle={"open": 0.20180, "high": 0.20190, "low": 0.20175, "close": 0.20184},
        tech_snapshot={"rsi_14": 52.4, "trend": "Bullish", "ema_20": 0.20170, "momentum_state": "Strong", "atr_14": 0.00015}
    )
    assert "LIVE ASSET MONITOR: USD/BRL (OTC)" in text
    assert "0.20184" in text
    assert "95%" in text
    assert "52.4" in text
    assert any("Refresh Live Price" in b["text"] for row in kb for b in row)
    assert any("Generate 1M Chart" in b["text"] for row in kb for b in row)
    assert any("Set Signal Alert" in b["text"] for row in kb for b in row)
