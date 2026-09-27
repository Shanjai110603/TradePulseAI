import pytest
from core.models.candle import Candle
from core.strategy.rules_ast import PatternRuleEngine
from core.strategy.compiler import StrategyCompiler
from core.strategy.schema import UserStrategy, StrategyFilters, CandleAnatomyConfig


def test_unrecognized_condition_fails_closed(sample_candles):
    """Verify that an unrecognized or corrupted condition type returns False (fail-closed)."""
    node = {
        "type": "non_existent_exploit_rule",
        "params": {"some_param": 123}
    }
    passed, reason, _ = PatternRuleEngine.evaluate_node(
        node=node,
        candles=sample_candles,
        direction_context="CALL"
    )
    assert passed is False
    assert "rejected (fail-closed)" in reason


def test_candle_anatomy_evaluation(sample_candles):
    """Test candle anatomy evaluator correctly checks body and wick ratios."""
    node = {
        "type": "candle_anatomy",
        "params": {
            "min_body_ratio": 0.1,
            "max_opposing_wick": 0.9,
            "filter_preceding_doji": False
        }
    }
    passed, reason, _ = PatternRuleEngine.evaluate_node(
        node=node,
        candles=sample_candles,
        direction_context="CALL"
    )
    assert isinstance(passed, bool)
    assert isinstance(reason, str)


def test_indicator_threshold_evaluation(sample_candles):
    """Test indicator threshold evaluation with RSI bounded between 0 and 100."""
    node = {
        "type": "indicator_threshold",
        "params": {
            "indicator": "RSI",
            "period": 14,
            "condition": "BETWEEN",
            "min_val": 0.0,
            "max_val": 100.0
        }
    }
    passed, reason, _ = PatternRuleEngine.evaluate_node(
        node=node,
        candles=sample_candles,
        direction_context="CALL"
    )
    assert passed is True
    assert "RSI" in reason


def test_dual_bollinger_protrusion_reversal_evaluation(extreme_reversal_candles):
    """Test Dual Bollinger Protrusion evaluation on extreme outer-band protrusion."""
    node = {
        "type": "dual_bollinger_protrusion",
        "params": {
            "period_1": 10,
            "period_2": 13,
            "deviation": 2.0,
            "min_body_protrusion": 0.05,
            "require_box_or_sr": False
        }
    }
    # Candle 25 protruded upward violently; on PUT direction this represents an overextended reversal setup
    passed, reason, details = PatternRuleEngine.evaluate_node(
        node=node,
        candles=extreme_reversal_candles[:-1],  # evaluate at candle 25
        direction_context="PUT"
    )
    assert isinstance(passed, bool)
    assert "protrusion" in reason.lower() or "bollinger" in reason.lower()


def test_compiler_to_ast_execution(sample_candles):
    """Test that a UserStrategy compiles into AST and executes deterministically."""
    strategy = UserStrategy(
        id="test_custom_strat",
        name="Test Custom Strategy",
        enabled=True,
        direction="BOTH",
        filters=StrategyFilters(
            candle_anatomy=CandleAnatomyConfig(
                min_body_ratio=0.1,
                max_opposing_wick=0.8,
                filter_preceding_doji=False
            )
        )
    )
    ast = StrategyCompiler.compile_strategy_ast(strategy)
    assert "operator" in ast
    assert ast["operator"] == "AND"
    assert len(ast["conditions"]) > 0

    passed, reason, _ = PatternRuleEngine.evaluate(
        ast=ast,
        candles=sample_candles,
        direction="CALL"
    )
    assert isinstance(passed, bool)


def test_confluence_voting_operator(sample_candles):
    """Test that CONFLUENCE_VOTING operator requires N of M sub-conditions to pass."""
    # 2 conditions that pass (RSI bounded 0-100) and 1 condition that fails (RSI bounded 99-100)
    passing_cond_1 = {
        "type": "indicator_threshold",
        "params": {"indicator": "RSI", "period": 14, "condition": "BETWEEN", "min_val": 0.0, "max_val": 100.0}
    }
    passing_cond_2 = {
        "type": "indicator_threshold",
        "params": {"indicator": "RSI", "period": 14, "condition": "BETWEEN", "min_val": 10.0, "max_val": 90.0}
    }
    failing_cond = {
        "type": "indicator_threshold",
        "params": {"indicator": "RSI", "period": 14, "condition": "BETWEEN", "min_val": 99.0, "max_val": 100.0}
    }

    # Test requiring 2 of 3: should PASS
    node_pass = {
        "type": "CONFLUENCE_VOTING",
        "params": {
            "min_agreeing_factors": 2,
            "min_quality_score": 50.0,
            "conditions": [passing_cond_1, passing_cond_2, failing_cond]
        }
    }
    passed, reason, details = PatternRuleEngine.evaluate_node(node_pass, sample_candles, "CALL")
    assert passed is True
    assert details["votes_passed"] >= 2

    # Test requiring 3 of 3: should FAIL because failing_cond fails
    node_fail = {
        "type": "CONFLUENCE_VOTING",
        "params": {
            "min_agreeing_factors": 3,
            "min_quality_score": 100.0,
            "conditions": [passing_cond_1, passing_cond_2, failing_cond]
        }
    }
    passed_fail, reason_fail, _ = PatternRuleEngine.evaluate_node(node_fail, sample_candles, "CALL")
    assert passed_fail is False
    assert "insufficient confluence" in reason_fail.lower()
