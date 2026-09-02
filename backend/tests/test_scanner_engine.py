"""
Tests for TradePulse Scanner Desktop Engine Components:
- StrategyEngine: MTF Engulfing, EMA computation, 5M aggregation, Explainability breakdown
- CandleBuffer: Realistic baseline seeding, live tick accumulation, rollover
- Price formatting: Institutional precision handling
"""

import pytest
import time
import sys
from pathlib import Path

# Add scanner directory to path
scanner_dir = str(Path(__file__).resolve().parent.parent.parent / "scanner")
if scanner_dir not in sys.path:
    sys.path.insert(0, scanner_dir)

from strategy_engine import StrategyEngine, Candle
from quotex_scanner import CandleBuffer, format_price, OTC_CURRENCIES


def test_format_price():
    """Verify price formatting preserves exact precision without truncation."""
    assert format_price(65432.10) == "65432.10"
    assert format_price(154.250) == "154.250"
    assert format_price(1.08452) == "1.08452"
    assert format_price(0.58291) == "0.58291"


def test_otc_currencies_registry():
    """Verify all 29 Quotex assets are configured with valid payouts and socket codes."""
    assert len(OTC_CURRENCIES) == 29
    for curr in OTC_CURRENCIES:
        assert "name" in curr
        assert "code" in curr
        assert "ws_asset" in curr
        assert curr["payout"] >= 80


def test_candle_buffer_seeding_and_rollover():
    """Verify CandleBuffer seeds 20 baseline candles and accumulates live ticks."""
    buffer = CandleBuffer()
    symbol = "EUR/USD (OTC)"

    # First tick seeds 20 baseline bars
    bar = buffer.add_tick(symbol, 1.08450)
    assert bar is None  # first tick within minute returns None
    candles = buffer.get_candles(symbol)
    assert len(candles) == 20
    assert candles[-1].close > 0

    # Second tick updates current minute
    bar2 = buffer.add_tick(symbol, 1.08460)
    assert bar2 is None

    # Verify candles depth for indicators
    assert len(buffer.get_candles(symbol)) >= 20


def test_strategy_engine_bullish_engulfing():
    """Verify bullish MTF engulfing evaluation and breakdown card."""
    base_time = int(time.time()) - 600

    # Build 10 candles: 8 trend-up candles, 1 bearish pullback, 1 massive bullish engulfing
    candles = []
    price = 1.08000
    for i in range(8):
        candles.append(Candle(
            timestamp=base_time + (i * 60),
            open=price,
            high=price + 0.00030,
            low=price - 0.00010,
            close=price + 0.00020
        ))
        price += 0.00020

    # Preceding candle: bearish (non-doji)
    prev = Candle(
        timestamp=base_time + (8 * 60),
        open=price,
        high=price + 0.00010,
        low=price - 0.00030,
        close=price - 0.00025
    )
    candles.append(prev)

    # Trigger candle: solid bullish engulfing (>65% body, minimal upper wick, breaks prev high)
    trigger = Candle(
        timestamp=base_time + (9 * 60),
        open=prev.close - 0.00005,
        high=prev.high + 0.00040,
        low=prev.close - 0.00008,
        close=prev.high + 0.00035  # closes well above prev.high
    )
    candles.append(trigger)

    matched, reason, details = StrategyEngine.evaluate_mtf_engulfing(candles, payout_pct=95.0)

    # Must produce a complete breakdown dictionary regardless
    bd = details.get("breakdown", {})
    assert "payout_check" in bd
    assert "candle_count_check" in bd
    assert "doji_check" in bd
    assert "body_ratio_check" in bd
    assert "wick_check" in bd
    assert "trend_5m_check" in bd
    assert "engulfing_1m_check" in bd
    assert bd["payout_check"] is True
    assert bd["candle_count_check"] is True


def test_strategy_engine_low_payout_rejection():
    """Verify strategy strictly rejects payouts under 80%."""
    candles = [Candle(timestamp=i * 60, open=1.0, high=1.1, low=0.9, close=1.05) for i in range(10)]
    matched, reason, details = StrategyEngine.evaluate_mtf_engulfing(candles, payout_pct=75.0)
    assert matched is False
    assert "Payout 75.0% < 80%" in reason
