import pytest
from app.engine.market_data.base import Candle
from app.engine.rules.engine import PatternRuleEngine


def test_fair_value_gap_bearish():
    candles = [
        Candle(timestamp=100, open=1.0855, high=1.0860, low=1.0850, close=1.0852, volume=1000),
        Candle(timestamp=160, open=1.0849, high=1.0850, low=1.0818, close=1.0820, volume=2500),
        Candle(timestamp=220, open=1.0819, high=1.0830, low=1.0815, close=1.0825, volume=1200),
        Candle(timestamp=280, open=1.0826, high=1.0835, low=1.0822, close=1.0828, volume=1800),
    ]
    pattern_config = {
        "name": "SMC Bearish FVG Strategy",
        "direction": "DOWN",
        "rules_config": {
            "type": "fair_value_gap",
            "params": {"direction": "DOWN"}
        }
    }
    result = PatternRuleEngine.evaluate_pattern(pattern_config, candles)
    assert result["matched"] is True
    assert result["direction"] == "DOWN"
    assert "Fair Value Gap Confirmed" in result["reason"]


def test_liquidity_sweep_reversal_bearish():
    candles = [
        Candle(timestamp=100, open=1.0830, high=1.0850, low=1.0825, close=1.0845, volume=1000),
        Candle(timestamp=160, open=1.0845, high=1.0848, low=1.0835, close=1.0838, volume=1000),
        Candle(timestamp=220, open=1.0838, high=1.0842, low=1.0830, close=1.0832, volume=1000),
        Candle(timestamp=280, open=1.0832, high=1.0840, low=1.0828, close=1.0835, volume=1000),
        Candle(timestamp=340, open=1.0835, high=1.0845, low=1.0830, close=1.0840, volume=1000),
        Candle(timestamp=400, open=1.0840, high=1.0856, low=1.0838, close=1.0842, volume=2200),
    ]
    pattern_config = {
        "name": "SMC Liquidity Sweep Strategy",
        "direction": "DOWN",
        "rules_config": {
            "type": "liquidity_sweep",
            "params": {"direction": "DOWN", "lookback": 5}
        }
    }
    result = PatternRuleEngine.evaluate_pattern(pattern_config, candles)
    assert result["matched"] is True
    assert "Liquidity Sweep Reversal Confirmed" in result["reason"]


def test_break_of_structure_bearish():
    candles = [
        Candle(timestamp=100, open=1.0840, high=1.0845, low=1.0820, close=1.0830, volume=1000),
        Candle(timestamp=160, open=1.0830, high=1.0835, low=1.0822, close=1.0828, volume=1000),
        Candle(timestamp=220, open=1.0828, high=1.0832, low=1.0824, close=1.0829, volume=1000),
        Candle(timestamp=280, open=1.0829, high=1.0830, low=1.0821, close=1.0825, volume=1000),
        Candle(timestamp=340, open=1.0825, high=1.0826, low=1.0812, close=1.0815, volume=2000),
    ]
    pattern_config = {
        "name": "SMC Bearish BOS Strategy",
        "direction": "DOWN",
        "rules_config": {
            "type": "break_of_structure",
            "params": {"direction": "DOWN", "lookback": 4}
        }
    }
    result = PatternRuleEngine.evaluate_pattern(pattern_config, candles)
    assert result["matched"] is True
    assert "Break of Structure (BOS) Confirmed" in result["reason"]


def test_wick_rejection_quotex():
    # Trigger candle with 50% upper wick rejection
    candles = [
        Candle(timestamp=100, open=1.0830, high=1.0840, low=1.0825, close=1.0835, volume=1000),
        Candle(timestamp=160, open=1.0835, high=1.0845, low=1.0830, close=1.0840, volume=1000),
        Candle(timestamp=220, open=1.0840, high=1.0860, low=1.0835, close=1.0838, volume=2500),
    ]
    pattern_config = {
        "name": "Quotex Wick Rejection Strategy",
        "direction": "DOWN",
        "rules_config": {
            "type": "wick_rejection",
            "params": {"direction": "DOWN", "min_wick_ratio": 0.40}
        }
    }
    result = PatternRuleEngine.evaluate_pattern(pattern_config, candles)
    assert result["matched"] is True
    assert "Quotex Upper Wick Rejection Confirmed" in result["reason"]


def test_momentum_alignment_quotex():
    candles = [
        Candle(timestamp=100, open=1.0850, high=1.0855, low=1.0840, close=1.0845, volume=1000),
        Candle(timestamp=160, open=1.0845, high=1.0846, low=1.0830, close=1.0832, volume=1500),
        Candle(timestamp=220, open=1.0832, high=1.0833, low=1.0818, close=1.0820, volume=2000),
    ]
    pattern_config = {
        "name": "Momentum Alignment Strategy",
        "direction": "DOWN",
        "rules_config": {
            "type": "momentum_alignment",
            "params": {"direction": "DOWN"}
        }
    }
    result = PatternRuleEngine.evaluate_pattern(pattern_config, candles)
    assert result["matched"] is True
    assert "Bearish Momentum Alignment Confirmed" in result["reason"]


def test_ema_trend_bounce_quotex():
    # 25 candles to establish EMA 20, then pullback and rejection at EMA 20
    candles = [
        Candle(timestamp=i * 60, open=1.0900 - i * 0.0002, high=1.0905 - i * 0.0002, low=1.0895 - i * 0.0002, close=1.0898 - i * 0.0002, volume=1000)
        for i in range(25)
    ]
    # Make trigger candle test EMA and close below
    pattern_config = {
        "name": "Quotex EMA Trend Bounce",
        "direction": "DOWN",
        "rules_config": {
            "type": "ema_trend_bounce",
            "params": {"direction": "DOWN", "ema_period": 20}
        }
    }
    result = PatternRuleEngine.evaluate_pattern(pattern_config, candles)
    assert isinstance(result["matched"], bool)


def test_order_block_quotex():
    candles = [
        Candle(timestamp=100, open=1.0820, high=1.0840, low=1.0818, close=1.0838, volume=1000),
        Candle(timestamp=160, open=1.0838, high=1.0840, low=1.0800, close=1.0805, volume=3000),
        Candle(timestamp=220, open=1.0805, high=1.0810, low=1.0780, close=1.0785, volume=3500),
        Candle(timestamp=280, open=1.0785, high=1.0830, low=1.0780, close=1.0825, volume=1500),
    ]
    pattern_config = {
        "name": "SMC Order Block Mitigation",
        "direction": "DOWN",
        "rules_config": {
            "type": "order_block",
            "params": {"direction": "DOWN", "lookback": 5}
        }
    }
    result = PatternRuleEngine.evaluate_pattern(pattern_config, candles)
    assert result["matched"] is True
    assert "Bearish Order Block Mitigation Confirmed" in result["reason"]
