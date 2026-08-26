import pytest
from app.engine.market_data.base import Candle
from app.engine.indicators.engine import TechnicalIndicatorEngine


def generate_sample_candles(count: int = 50, trend: str = "downtrend") -> list[Candle]:
    candles = []
    p = 100.0
    for i in range(count):
        if trend == "downtrend":
            o = p
            c = o - 0.5
            h = o + 0.2
            l = c - 0.2
        elif trend == "uptrend":
            o = p
            c = o + 0.5
            h = c + 0.2
            l = o - 0.2
        else:
            o = p
            c = o + (0.1 if i % 2 == 0 else -0.1)
            h = max(o, c) + 0.1
            l = min(o, c) - 0.1
        candles.append(Candle(timestamp=1700000000 + i * 60, open=o, high=h, low=l, close=c, volume=1000.0))
        p = c
    return candles


def test_sma_calculation():
    prices = [10.0, 11.0, 12.0, 13.0, 14.0]
    sma = TechnicalIndicatorEngine.calculate_sma(prices, period=3)
    assert sma[0] is None
    assert sma[1] is None
    assert sma[2] == pytest.approx(11.0)
    assert sma[3] == pytest.approx(12.0)
    assert sma[4] == pytest.approx(13.0)


def test_ema_calculation():
    prices = [10.0, 11.0, 12.0, 13.0, 14.0]
    ema = TechnicalIndicatorEngine.calculate_ema(prices, period=3)
    assert ema[0] is None
    assert ema[1] is None
    assert ema[2] == pytest.approx(11.0)
    assert ema[3] > 11.0


def test_rsi_calculation():
    candles_down = generate_sample_candles(30, "downtrend")
    rsi_down = TechnicalIndicatorEngine.calculate_rsi(candles_down, 14)
    assert rsi_down[-1] is not None
    assert rsi_down[-1] < 30.0  # Strongly oversold in downtrend

    candles_up = generate_sample_candles(30, "uptrend")
    rsi_up = TechnicalIndicatorEngine.calculate_rsi(candles_up, 14)
    assert rsi_up[-1] is not None
    assert rsi_up[-1] > 70.0  # Strongly overbought in uptrend


def test_bollinger_bands():
    candles = generate_sample_candles(30, "flat")
    bb = TechnicalIndicatorEngine.calculate_bollinger_bands(candles, period=20)
    assert bb["upper"][-1] is not None
    assert bb["lower"][-1] is not None
    assert bb["upper"][-1] > bb["middle"][-1] > bb["lower"][-1]


def test_technical_snapshot():
    candles = generate_sample_candles(40, "downtrend")
    snapshot = TechnicalIndicatorEngine.calculate_technical_snapshot(candles)
    assert "rsi" in snapshot
    assert "macd" in snapshot
    assert "ema_fast" in snapshot
    assert "market_structure" in snapshot
    assert snapshot["market_structure"]["trend"] == "BEARISH"
