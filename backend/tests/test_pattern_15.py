import pytest
from app.engine.market_data.base import Candle
from app.engine.rules.engine import PatternRuleEngine


@pytest.fixture
def pattern_15_config():
    return {
        "id": "test-pat-15",
        "name": "Pattern Type 15 (V-Pattern Resistance Rejection)",
        "market_id": "digital_options",
        "direction": "DOWN",
        "timeframe": "1M",
        "asset_symbol": "EUR/USD (OTC)",
        "current_version": 1,
        "trend_config": {},
        "momentum_config": {},
        "volume_config": {},
        "rules_config": {
            "operator": "AND",
            "conditions": [
                {
                    "type": "pattern_type_15",
                    "params": {
                        "lookback": 10
                    }
                }
            ]
        },
        "target_config": {"duration_minutes": 1, "duration_candles": 1},
        "ai_config": {"enabled": True, "min_score": 75, "required_bias": "BEARISH"}
    }


def test_pattern_15_v_reversal_match(pattern_15_config):
    """
    Validates Pattern Type 15 (V-Pattern Resistance Rejection):
    1. Left resistance level at 1.08600.
    2. Drop down to swing low at 1.08400 (V-bottom).
    3. Strong rally up to test 1.08600.
    4. Trigger candle pierces 1.08600 and rejects with upper wick / bearish close.
    """
    candles = []
    # 1. Left shoulder: 1.08580 -> 1.08600 (horizontal line)
    candles.append(Candle(timestamp=1700000000, open=1.08550, high=1.08600, low=1.08540, close=1.08590, volume=100.0))
    candles.append(Candle(timestamp=1700000060, open=1.08590, high=1.08595, low=1.08530, close=1.08540, volume=110.0))
    
    # 2. Down leg of V: dropping to 1.08400
    candles.append(Candle(timestamp=1700000120, open=1.08540, high=1.08545, low=1.08480, close=1.08490, volume=120.0))
    candles.append(Candle(timestamp=1700000180, open=1.08490, high=1.08500, low=1.08440, close=1.08450, volume=130.0))
    candles.append(Candle(timestamp=1700000240, open=1.08450, high=1.08460, low=1.08400, close=1.08410, volume=140.0)) # Swing Low Bottom

    # 3. Up leg of V: rally back up to 1.08600
    candles.append(Candle(timestamp=1700000300, open=1.08410, high=1.08470, low=1.08405, close=1.08460, volume=130.0))
    candles.append(Candle(timestamp=1700000360, open=1.08460, high=1.08520, low=1.08455, close=1.08510, volume=140.0))
    candles.append(Candle(timestamp=1700000420, open=1.08510, high=1.08570, low=1.08505, close=1.08560, volume=150.0))
    candles.append(Candle(timestamp=1700000480, open=1.08560, high=1.08610, low=1.08555, close=1.08605, volume=160.0)) # Breaks horizontal line

    # 4. Trigger candle: Rejection with upper wick / bearish close back below resistance
    candles.append(Candle(timestamp=1700000540, open=1.08605, high=1.08625, low=1.08560, close=1.08570, volume=180.0))

    result = PatternRuleEngine.evaluate_pattern(pattern_15_config, candles)

    assert result["matched"] is True
    assert result["direction"] == "DOWN"
    assert result["resistance_level"] is not None
    assert "Pattern Type 15 Confirmed" in result["reason"]
