"""
Tests for Visual Strategy Studio backend APIs, in-trade cooldown lockout, and authentic candle evaluation.
"""
import time
import pytest
from core.models.candle import Candle
from core.strategy.schema import UserStrategy
from core.strategy.backtest import HistoricalBacktestEngine
from core.ingester.real_market_feed import RealMarketFeed

def create_sample_candles(count=100, base_price=1.1000):
    candles = []
    ts = int(time.time()) - (count * 60)
    price = base_price
    for i in range(count):
        # Oscillating wave with authentic spread
        delta = 0.0004 if (i % 6) < 3 else -0.0004
        c_open = price
        c_close = price + delta
        c_high = max(c_open, c_close) + 0.0002
        c_low = min(c_open, c_close) - 0.0002
        candles.append(Candle(
            timestamp=ts + (i * 60),
            open=c_open,
            high=c_high,
            low=c_low,
            close=c_close,
            volume=150.0
        ))
        price = c_close
    return candles

def test_backtest_engine_in_trade_cooldown_lockout():
    """Verify that multiple signals cannot fire within the active trade lockout window."""
    candles = create_sample_candles(count=80)
    strat = UserStrategy(
        id="test_lockout",
        name="Test Lockout Strategy",
        timeframe="1M",
        expiry_minutes=2,
        cooldown_seconds=180,  # 3 bars
        direction="BOTH",
        filters={
            "candle_anatomy": {"min_body_ratio": 0.10, "max_opposing_wick": 0.60},
            "confluence": {"min_factors": 0}
        }
    )

    res = HistoricalBacktestEngine.test_strategy_on_asset(strat, candles, [], payout_pct=85.0)
    assert "total_signals" in res
    assert "win_rate" in res
    assert "results_log" in res

    # Verify that consecutive trades in results_log respect lockout
    logs = res["results_log"]
    if len(logs) >= 2:
        for i in range(1, len(logs)):
            prev_ts = logs[i - 1]["timestamp"]
            curr_ts = logs[i]["timestamp"]
            assert (curr_ts - prev_ts) >= 180, f"Signals fired too close: {prev_ts} vs {curr_ts}"

def test_sample_candle_organic_spread():
    """Verify sample candle generation creates realistic, authentic spreads with non-zero wicks."""
    candles = create_sample_candles(100)
    assert len(candles) == 100
    for c in candles:
        assert c.high > c.low, "Candle has zero or inverted spread"
        assert c.high >= c.open and c.high >= c.close
        assert c.low <= c.open and c.low <= c.close
        assert c.volume > 0
