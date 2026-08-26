import pytest
from app.engine.market_data.base import Candle
from app.engine.rules.engine import PatternRuleEngine


def test_ast_and_or_not_operators():
    # Construct a sample sequence of candles
    candles = [
        Candle(timestamp=100, open=1.0, high=1.2, low=0.9, close=0.95, volume=100),  # Bearish
        Candle(timestamp=160, open=0.95, high=1.3, low=0.9, close=1.25, volume=150), # Bullish
    ]

    # Test AND node
    and_config = {
        "rules_config": {
            "operator": "AND",
            "conditions": [
                {"type": "candle_color", "params": {"index": -1, "color": "bullish"}},
                {"type": "candle_color", "params": {"index": -2, "color": "bearish"}}
            ]
        }
    }
    res = PatternRuleEngine.evaluate_pattern(and_config, candles + [Candle(timestamp=220, open=1.0, high=1.1, low=0.9, close=1.05, volume=100), Candle(timestamp=280, open=1.05, high=1.1, low=0.9, close=1.08, volume=100), Candle(timestamp=340, open=1.08, high=1.1, low=0.9, close=1.09, volume=100)])
    # The last 3 candles are bullish, so index -1 is bullish, index -2 is bullish
    # Let's test precisely on 5 candles
    c5 = [
        Candle(timestamp=100, open=1.0, high=1.1, low=0.8, close=0.9, volume=100), # -5 Bearish
        Candle(timestamp=160, open=0.9, high=1.1, low=0.8, close=0.85, volume=100), # -4 Bearish
        Candle(timestamp=220, open=0.85, high=1.1, low=0.8, close=0.8, volume=100), # -3 Bearish
        Candle(timestamp=280, open=0.8, high=1.0, low=0.7, close=0.75, volume=100), # -2 Bearish
        Candle(timestamp=340, open=0.75, high=1.1, low=0.7, close=0.95, volume=100), # -1 Bullish
    ]
    res = PatternRuleEngine.evaluate_pattern(and_config, c5)
    assert res["matched"] is True

    # Test OR node
    or_config = {
        "rules_config": {
            "operator": "OR",
            "conditions": [
                {"type": "candle_color", "params": {"index": -1, "color": "bearish"}},
                {"type": "candle_color", "params": {"index": -1, "color": "bullish"}}
            ]
        }
    }
    res_or = PatternRuleEngine.evaluate_pattern(or_config, c5)
    assert res_or["matched"] is True

    # Test NOT node
    not_config = {
        "rules_config": {
            "operator": "NOT",
            "conditions": [
                {"type": "candle_color", "params": {"index": -1, "color": "bearish"}}
            ]
        }
    }
    res_not = PatternRuleEngine.evaluate_pattern(not_config, c5)
    assert res_not["matched"] is True  # Because index -1 is bullish, not bearish!
