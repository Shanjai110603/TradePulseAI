import pytest
from app.engine.market_data.base import Candle
from app.engine.rules.engine import PatternRuleEngine


@pytest.fixture
def pattern_1_config():
    return {
        "id": "test-pat-1",
        "name": "Pattern Type 1 (SMC 10 Line Reversal)",
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
                    "type": "pattern_type_1",
                    "params": {
                        "smc_period": 10
                    }
                }
            ]
        },
        "target_config": {"duration_minutes": 1, "duration_candles": 1},
        "ai_config": {"enabled": True, "min_score": 75, "required_bias": "BEARISH"}
    }


def test_pattern_1_deterministic_match(pattern_1_config):
    """
    Validates Pattern Type 1:
    - 10 candles above the current price to set a high SMC 10 Line
    - Candle -3: Green (Bullish)
    - Candle -2: Green (Bullish)
    - Candle -1: Red (Bearish reversal)
    - All 3 candles below SMC 10 Line
    """
    candles = []
    # Build 10 base candles at price ~1.10000 so SMC 10 line is ~1.10000
    for i in range(10):
        candles.append(Candle(
            timestamp=1700000000 + (i * 60),
            open=1.10000,
            high=1.10050,
            low=1.09950,
            close=1.10000,
            volume=100.0
        ))

    # Candle -3: 1st Green candle (1.08500 -> 1.08540)
    candles.append(Candle(
        timestamp=1700000600,
        open=1.08500,
        high=1.08550,
        low=1.08490,
        close=1.08540,
        volume=120.0
    ))

    # Candle -2: 2nd Green candle (1.08540 -> 1.08580)
    candles.append(Candle(
        timestamp=1700000660,
        open=1.08540,
        high=1.08600,
        low=1.08530,
        close=1.08580,
        volume=130.0
    ))

    # Candle -1: 3rd Red trigger candle (1.08580 -> 1.08520)
    candles.append(Candle(
        timestamp=1700000720,
        open=1.08580,
        high=1.08590,
        low=1.08510,
        close=1.08520,
        volume=140.0
    ))

    result = PatternRuleEngine.evaluate_pattern(pattern_1_config, candles)

    assert result["matched"] is True
    assert result["direction"] == "DOWN"
    assert result["support_level"] is not None or result["resistance_level"] is not None
    assert "Pattern Type 1 Confirmed" in result["reason"]
