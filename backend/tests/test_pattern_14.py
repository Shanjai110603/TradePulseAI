import pytest
from app.engine.market_data.mock_provider import MockDataProvider
from app.engine.rules.engine import PatternRuleEngine
from app.engine.signals.evaluator import SignalEvaluationPipeline
from app.engine.ai.mock_ai import MockAIProvider


@pytest.fixture
def pattern_14_config():
    return {
        "id": "test-pat-14",
        "name": "Pattern Type 14 Test",
        "market_id": "digital_options",
        "direction": "DOWN",
        "timeframe": "1M",
        "asset_symbol": "EUR/USD",
        "current_version": 1,
        "trend_config": {"required": "Any"},
        "momentum_config": {"strength": "Any"},
        "volume_config": {"type": "Any"},
        "rules_config": {
            "operator": "AND",
            "conditions": [
                {
                    "type": "pattern_type_14",
                    "params": {
                        "bullish_count": 2,
                        "confirmation": "close_below",
                        "support_source": "swing_low"
                    }
                }
            ]
        },
        "target_config": {"duration_minutes": 5, "duration_candles": 5},
        "ai_config": {"enabled": True, "min_score": 70, "required_bias": "ANY"}
    }


def test_pattern_14_exact_match(pattern_14_config):
    """Proves that a valid Pattern Type 14 sequence triggers a DOWN signal deterministically"""
    candles = MockDataProvider.generate_pattern_14_fixture(
        base_price=1.08500,
        support_break_type="close_below"
    )
    result = PatternRuleEngine.evaluate_pattern(pattern_14_config, candles)
    
    assert result["matched"] is True
    assert result["direction"] == "DOWN"
    assert result["support_level"] is not None


def test_pattern_14_inverted_exact_match():
    """Proves that an inverted Pattern Type 14 triggers an UP signal deterministically"""
    config = {
        "id": "test-pat-14-inv",
        "name": "Inverted Pattern Type 14",
        "direction": "UP",
        "trend_config": {"required": "Any"},
        "momentum_config": {"strength": "Any"},
        "volume_config": {"type": "Any"},
        "rules_config": {
            "operator": "AND",
            "conditions": [
                {
                    "type": "pattern_type_14_inverted",
                    "params": {
                        "bearish_count": 2,
                        "confirmation": "close_above",
                        "resistance_source": "swing_high"
                    }
                }
            ]
        }
    }
    candles = MockDataProvider.generate_inverted_pattern_14_fixture(
        base_price=1.08500,
        resistance_break_type="close_above"
    )
    result = PatternRuleEngine.evaluate_pattern(config, candles)
    assert result["matched"] is True
    assert result["direction"] == "UP"
    assert result["resistance_level"] is not None


def test_pattern_14_failure_wick_only_break(pattern_14_config):
    """Proves that if only the wick pierces support but close stays above, it FAILS confirmation"""
    candles = MockDataProvider.generate_pattern_14_fixture(
        base_price=1.08500,
        support_break_type="wick_only"
    )
    result = PatternRuleEngine.evaluate_pattern(pattern_14_config, candles)
    assert result["matched"] is False
    assert "failed" in result["reason"].lower() or "not satisfied" in result["reason"].lower()


def test_pattern_14_failure_no_break(pattern_14_config):
    """Proves that if support is never reached, the pattern FAILS"""
    candles = MockDataProvider.generate_pattern_14_fixture(
        base_price=1.08500,
        support_break_type="no_break"
    )
    result = PatternRuleEngine.evaluate_pattern(pattern_14_config, candles)
    assert result["matched"] is False


def test_pattern_14_failure_wrong_candle_count(pattern_14_config):
    """Proves that if configured for 3 bullish candles but fixture has 2, it FAILS"""
    pattern_14_config["rules_config"]["conditions"][0]["params"]["bullish_count"] = 3
    candles = MockDataProvider.generate_pattern_14_fixture(
        base_price=1.08500,
        support_break_type="close_below"
    )
    result = PatternRuleEngine.evaluate_pattern(pattern_14_config, candles)
    assert result["matched"] is False


@pytest.mark.asyncio
async def test_pattern_14_full_pipeline_with_ai(pattern_14_config):
    """Tests end-to-end evaluation pipeline with AI enrichment and user filter checks"""
    candles = MockDataProvider.generate_pattern_14_fixture(
        base_price=1.08500,
        support_break_type="close_below"
    )
    is_created, payload, reason, audit = await SignalEvaluationPipeline.evaluate_candidate(
        pattern_dict=pattern_14_config,
        candles=candles
    )
    if not is_created:
        print(f"\nDEBUG FAILURE REASON: {reason}\nAUDIT: {audit}\n")
    assert is_created is True
    assert payload is not None
    assert payload["direction"] == "DOWN"
    assert payload["ai_score"] >= 70
    assert payload["status"] == "ACTIVE"
    assert "ai_analysis" in payload
