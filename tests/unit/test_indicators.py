import pytest
from core.indicators.engine import TechnicalIndicatorEngine


def test_calculate_ema(sample_candles):
    """Test EMA calculation returns accurate float values across standard periods."""
    ema20 = TechnicalIndicatorEngine.calculate_ema(sample_candles, 20)
    ema50 = TechnicalIndicatorEngine.calculate_ema(sample_candles, 50)

    assert ema20 is not None
    assert ema50 is not None
    assert isinstance(ema20, float)
    assert isinstance(ema50, float)
    assert 1.07 < ema20 < 1.10
    assert 1.07 < ema50 < 1.10


def test_calculate_rsi(sample_candles):
    """Test RSI calculation produces values bounded strictly between 0 and 100."""
    rsi = TechnicalIndicatorEngine.calculate_rsi(sample_candles, 14)

    assert rsi is not None
    assert isinstance(rsi, float)
    assert 0.0 <= rsi <= 100.0


def test_calculate_bollinger_bands(sample_candles):
    """Test Bollinger Bands return valid upper, middle, and lower lines."""
    bb = TechnicalIndicatorEngine.calculate_bollinger_bands(sample_candles, period=20, std_dev_multiplier=2.0)

    assert bb is not None
    assert "upper" in bb
    assert "middle" in bb
    assert "lower" in bb
    assert bb["upper"] >= bb["middle"] >= bb["lower"]
    assert bb["bandwidth"] > 0


def test_calculate_candlestick_formations(sample_candles):
    """Test candlestick formation identification returns expected structure."""
    formations = TechnicalIndicatorEngine.calculate_candlestick_formations(sample_candles)

    assert isinstance(formations, dict)
    assert "pinbar_bullish" in formations
    assert "pinbar_bearish" in formations
    assert "engulfing_bullish" in formations
    assert "engulfing_bearish" in formations
    assert "detected_patterns" in formations
    assert isinstance(formations["detected_patterns"], list)


def test_calculate_smc_structure(sample_candles):
    """Test Smart Money Concepts structure engine identifies fair value gaps and liquidity."""
    smc = TechnicalIndicatorEngine.calculate_smc_structure(sample_candles)

    assert isinstance(smc, dict)
    assert "fvg_bullish" in smc
    assert "fvg_bearish" in smc
    assert "liquidity_sweep_bullish" in smc
    assert "liquidity_sweep_bearish" in smc
    assert "bos_bullish" in smc
    assert "bos_bearish" in smc
