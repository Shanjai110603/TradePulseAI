import sys
import time
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models.candle import Candle


@pytest.fixture
def sample_candles():
    """Generates 100 realistic synthetic 1-minute OHLCV candles with upward trend and pullback."""
    candles = []
    base_price = 1.0800
    now = int(time.time()) - (100 * 60)

    for i in range(100):
        # Create a wave pattern
        delta = (i % 10 - 5) * 0.0002 + (i * 0.00005)
        open_p = round(base_price + delta, 5)
        high_p = round(open_p + 0.0005, 5)
        low_p = round(open_p - 0.0004, 5)
        close_p = round(open_p + 0.0002, 5)
        vol = 100.0 + (i * 2.0)
        c = Candle(
            timestamp=now + (i * 60),
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=vol
        )
        candles.append(c)
    return candles


@pytest.fixture
def extreme_reversal_candles():
    """Generates a sequence of candles simulating an extreme upper Bollinger Band breakout and reversal."""
    candles = []
    base_price = 1.1000
    now = int(time.time()) - (30 * 60)

    for i in range(25):
        # Flat consolidation
        candles.append(Candle(
            timestamp=now + (i * 60),
            open=round(base_price + 0.0001 * (i % 2), 5),
            high=round(base_price + 0.0003, 5),
            low=round(base_price - 0.0002, 5),
            close=round(base_price + 0.0001, 5),
            volume=50.0
        ))

    # Candle 25: Massive upward spike protrudes far beyond bands
    candles.append(Candle(
        timestamp=now + (25 * 60),
        open=round(base_price + 0.0001, 5),
        high=round(base_price + 0.0025, 5),
        low=round(base_price, 5),
        close=round(base_price + 0.0024, 5),
        volume=500.0
    ))

    # Candle 26: Strong bearish rejection pinbar
    candles.append(Candle(
        timestamp=now + (26 * 60),
        open=round(base_price + 0.0024, 5),
        high=round(base_price + 0.0027, 5),
        low=round(base_price + 0.0010, 5),
        close=round(base_price + 0.0012, 5),
        volume=600.0
    ))
    return candles
