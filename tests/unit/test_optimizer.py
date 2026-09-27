import pytest
from core.strategy.optimizer import StrategyOptimizer


def test_rsi_bollinger_grid_search(sample_candles):
    """Test StrategyOptimizer grid search sweeps parameter configurations."""
    res = StrategyOptimizer.run_rsi_bollinger_grid_search(sample_candles, payout_pct=85.0)

    assert isinstance(res, list)
    assert len(res) > 0

    for item in res[:5]:
        assert "rsi_period" in item
        assert "rsi_overbought" in item
        assert "rsi_oversold" in item
        assert "bb_deviation" in item
        assert "win_rate" in item
        assert "total_trades" in item
        assert "expected_value_per_trade" in item
        assert "profit_factor" in item
        assert "half_kelly_pct" in item
        assert 0.0 <= item["win_rate"] <= 100.0


def test_monte_carlo_permutation_test():
    """Test Monte Carlo permutation engine runs simulations and returns statistical metrics."""
    res = StrategyOptimizer.run_monte_carlo_permutation_test(
        wins=35,
        losses=15,
        payout_pct=85.0,
        simulations=500,
        stake=10.0
    )

    assert isinstance(res, dict)
    assert res.get("simulations") == 500
    assert "max_drawdown_p95" in res
    assert "max_consecutive_losses_p95" in res
    assert "ruin_probability_pct" in res
    assert "median_profit" in res

    # 35 wins out of 50 on 85% payout has a positive edge, median profit should be positive
    assert res["median_profit"] > 0
    assert res["max_consecutive_losses_p95"] >= 1
    assert 0.0 <= res["ruin_probability_pct"] <= 100.0
