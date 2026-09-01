import pytest
from app.engine.market_data.base import Candle
from app.engine.rules.engine import PatternRuleEngine


def test_mtf_engulfing_call_success():
    # 1M candles: preceding red, current bullish engulfing
    candles_1m = []
    # Build 25 flat candles around 1.08000 for EMA 20
    for i in range(25):
        candles_1m.append(Candle(open=1.0800, high=1.0805, low=1.0795, close=1.0800, volume=100, timestamp=1000 + i * 60))
    
    # Preceding candle (Red): Open 1.0810, High 1.0812, Low 1.0800, Close 1.0802 (Range 0.0012, Body 0.0008 = 66%)
    candles_1m.append(Candle(open=1.0810, high=1.0812, low=1.0800, close=1.0802, volume=150, timestamp=3000))
    
    # Current Engulfing candle (Green): Open 1.0800, Low 1.0799, Close 1.0825, High 1.0826
    # Range = 0.0027, Body = 0.0025 (92.5% > 65%), Close > Preceding High (1.0825 > 1.0812)
    # Upper wick = 0.0001 (3.7% < 30%)
    candles_1m.append(Candle(open=1.0800, high=1.0826, low=1.0799, close=1.0825, volume=300, timestamp=3060))

    # 5M candles (Green + trading strictly above EMA 20)
    candles_5m = [
        Candle(open=1.0780, high=1.0790, low=1.0775, close=1.0785, volume=500, timestamp=1000),
        Candle(open=1.0785, high=1.0830, low=1.0780, close=1.0825, volume=800, timestamp=1300)
    ]

    snapshot = {
        "payout_pct": 85,
        "support_levels": [1.0750],
        "resistance_levels": [1.0900]
    }
    params = {"direction": "CALL", "payout_pct": 85}

    passed, reason, ctx = PatternRuleEngine._evaluate_mtf_engulfing_1m(
        candles=candles_1m,
        params=params,
        snapshot=snapshot,
        multi_timeframe_candles={"5M": candles_5m}
    )

    assert passed is True
    assert ctx["direction"] == "UP"
    assert ctx["expiry_minutes"] == 2


def test_mtf_engulfing_put_success():
    # 1M candles: preceding green, current bearish engulfing
    candles_1m = []
    for i in range(25):
        candles_1m.append(Candle(open=1.0850, high=1.0855, low=1.0845, close=1.0850, volume=100, timestamp=1000 + i * 60))
    
    # Preceding candle (Green): Open 1.0840, High 1.0850, Low 1.0838, Close 1.0848 (Range 0.0012, Body 0.0008 = 66%)
    candles_1m.append(Candle(open=1.0840, high=1.0850, low=1.0838, close=1.0848, volume=150, timestamp=3000))
    
    # Current Engulfing candle (Red): Open 1.0850, High 1.0851, Low 1.0820, Close 1.0822
    # Range = 0.0031, Body = 0.0028 (90.3% > 65%), Close < Preceding Low (1.0822 < 1.0838)
    # Lower wick = 0.0002 (6.4% < 30%)
    candles_1m.append(Candle(open=1.0850, high=1.0851, low=1.0820, close=1.0822, volume=300, timestamp=3060))

    # 5M candles (Red + trading strictly below EMA 20)
    candles_5m = [
        Candle(open=1.0890, high=1.0895, low=1.0880, close=1.0885, volume=500, timestamp=1000),
        Candle(open=1.0885, high=1.0888, low=1.0820, close=1.0822, volume=800, timestamp=1300)
    ]

    snapshot = {
        "payout_pct": 92,
        "support_levels": [1.0700],
        "resistance_levels": [1.0950]
    }
    params = {"direction": "PUT", "payout_pct": 92}

    passed, reason, ctx = PatternRuleEngine._evaluate_mtf_engulfing_1m(
        candles=candles_1m,
        params=params,
        snapshot=snapshot,
        multi_timeframe_candles={"5M": candles_5m}
    )

    assert passed is True
    assert ctx["direction"] == "DOWN"
    assert ctx["expiry_minutes"] == 2


def test_mtf_engulfing_avoid_low_payout():
    candles_1m = [Candle(open=1.0, high=1.1, low=0.9, close=1.05, volume=100, timestamp=1000 + i * 60) for i in range(30)]
    snapshot = {"payout_pct": 75}
    params = {"payout_pct": 75}

    passed, reason, _ = PatternRuleEngine._evaluate_mtf_engulfing_1m(candles_1m, params, snapshot)
    assert passed is False
    assert "Avoid Rule 1" in reason


def test_mtf_engulfing_avoid_doji_preceding():
    candles_1m = [Candle(open=1.0800, high=1.0805, low=1.0795, close=1.0800, volume=100, timestamp=1000 + i * 60) for i in range(25)]
    # Preceding candle is a Doji (Open 1.0800, Close 1.08005, High 1.0810, Low 1.0790 -> Body 0.00005, Range 0.0020 = 2.5% < 10%)
    candles_1m.append(Candle(open=1.0800, high=1.0810, low=1.0790, close=1.08005, volume=100, timestamp=3000))
    candles_1m.append(Candle(open=1.0800, high=1.0830, low=1.0799, close=1.0828, volume=200, timestamp=3060))

    passed, reason, _ = PatternRuleEngine._evaluate_mtf_engulfing_1m(candles_1m, {"direction": "CALL"}, {"payout_pct": 85})
    assert passed is False
    assert "Avoid Rule 4" in reason
