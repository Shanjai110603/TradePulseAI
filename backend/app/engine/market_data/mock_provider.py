import time
import math
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.engine.market_data.base import MarketDataProvider, Candle


class MockDataProvider(MarketDataProvider):
    """
    High-fidelity deterministic mock and simulation market data provider.
    Supports synthetic random-walk data generation, realistic volatility,
    and deterministic pattern injection (such as Pattern Type 14 fixtures).
    """

    BASE_PRICES = {
        # Digital Options & Forex
        "EUR/USD": 1.08500,
        "GBP/USD": 1.27200,
        "USD/JPY": 154.500,
        "AUD/USD": 0.65800,
        "USD/CAD": 1.36500,
        # Crypto
        "BTC/USDT": 67500.0,
        "ETH/USDT": 3450.0,
        "SOL/USDT": 145.0,
        "BNB/USDT": 590.0,
        # Stocks & Indices
        "AAPL": 225.0,
        "NVDA": 128.0,
        "TSLA": 210.0,
        "SPY": 555.0,
        "QQQ": 480.0,
    }

    TIMEFRAME_SECONDS = {
        "1M": 60,
        "5M": 300,
        "15M": 900,
        "30M": 1800,
        "1H": 3600,
        "4H": 14400,
        "1D": 86400,
    }

    def __init__(self, seed: Optional[int] = 42):
        self._seed = seed
        self._pattern_injection_active = False
        self._custom_fixtures: Dict[str, List[Candle]] = {}

    def get_provider_name(self) -> str:
        return "mock"

    def is_live(self) -> bool:
        return False  # Deterministic simulation

    def get_supported_timeframes(self) -> List[str]:
        return ["1M", "5M", "15M", "30M", "1H", "4H", "1D"]

    async def get_assets(self, market_id: str) -> List[Dict[str, Any]]:
        assets_by_market = {
            "digital_options": [
                {"symbol": "EUR/USD", "name": "Euro / US Dollar", "precision": 5, "min_movement": 0.00001},
                {"symbol": "GBP/USD", "name": "British Pound / US Dollar", "precision": 5, "min_movement": 0.00001},
                {"symbol": "USD/JPY", "name": "US Dollar / Japanese Yen", "precision": 3, "min_movement": 0.001},
                {"symbol": "AUD/USD", "name": "Australian Dollar / US Dollar", "precision": 5, "min_movement": 0.00001},
            ],
            "crypto": [
                {"symbol": "BTC/USDT", "name": "Bitcoin / Tether", "precision": 2, "min_movement": 0.01},
                {"symbol": "ETH/USDT", "name": "Ethereum / Tether", "precision": 2, "min_movement": 0.01},
                {"symbol": "SOL/USDT", "name": "Solana / Tether", "precision": 2, "min_movement": 0.01},
                {"symbol": "BNB/USDT", "name": "Binance Coin / Tether", "precision": 2, "min_movement": 0.01},
            ],
            "forex": [
                {"symbol": "EUR/USD", "name": "Euro / US Dollar", "precision": 5, "min_movement": 0.00001},
                {"symbol": "GBP/USD", "name": "British Pound / US Dollar", "precision": 5, "min_movement": 0.00001},
                {"symbol": "USD/JPY", "name": "US Dollar / Japanese Yen", "precision": 3, "min_movement": 0.001},
            ],
            "stocks": [
                {"symbol": "AAPL", "name": "Apple Inc.", "precision": 2, "min_movement": 0.01},
                {"symbol": "NVDA", "name": "NVIDIA Corporation", "precision": 2, "min_movement": 0.01},
                {"symbol": "TSLA", "name": "Tesla Inc.", "precision": 2, "min_movement": 0.01},
                {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "precision": 2, "min_movement": 0.01},
            ],
        }
        return assets_by_market.get(market_id, assets_by_market["digital_options"])

    async def get_current_price(self, symbol: str) -> float:
        base = self.BASE_PRICES.get(symbol, 100.0)
        # Small deterministic fluctuation based on current timestamp
        now = int(time.time())
        variation = math.sin(now / 15.0) * (base * 0.0008)
        return round(base + variation, 5 if "USD" in symbol and "BTC" not in symbol else 2)

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1M",
        limit: int = 100,
        end_time: Optional[datetime] = None
    ) -> List[Candle]:
        if symbol in self._custom_fixtures:
            candles = self._custom_fixtures[symbol]
            return candles[-limit:] if len(candles) > limit else candles

        tf_sec = self.TIMEFRAME_SECONDS.get(timeframe, 60)
        end_ts = int(end_time.timestamp()) if end_time else int(time.time())
        # Align to timeframe boundary
        end_ts = (end_ts // tf_sec) * tf_sec

        base_price = self.BASE_PRICES.get(symbol, 100.0)
        volatility = 0.0006 if "USD" in symbol and "BTC" not in symbol else 0.0025

        candles: List[Candle] = []
        current_price = base_price

        # Deterministic generation using symbol and timeframe
        rng = random.Random(f"{symbol}_{timeframe}_{self._seed}_{limit}")

        # Start from limit intervals ago
        start_ts = end_ts - (limit * tf_sec)

        for i in range(limit):
            ts = start_ts + (i * tf_sec)
            
            # Underlying cyclical trend + micro noise
            cycle = math.sin((i / limit) * 4 * math.pi) * 0.002
            pct_change = (rng.gauss(0, 1) * volatility) + (cycle * 0.001)

            open_p = current_price
            close_p = open_p * (1.0 + pct_change)
            
            # High and Low wicks
            max_body = max(open_p, close_p)
            min_body = min(open_p, close_p)
            
            high_wick = abs(rng.gauss(0, 1)) * (open_p * volatility * 0.8)
            low_wick = abs(rng.gauss(0, 1)) * (open_p * volatility * 0.8)
            
            high_p = max_body + high_wick
            low_p = max(min_body - low_wick, 0.0001)
            
            # Volume
            vol = abs(rng.gauss(1000, 250)) * (1.0 + abs(pct_change) * 50)

            candles.append(Candle(
                timestamp=ts,
                open=round(open_p, 5 if base_price < 10 else 2),
                high=round(high_p, 5 if base_price < 10 else 2),
                low=round(low_p, 5 if base_price < 10 else 2),
                close=round(close_p, 5 if base_price < 10 else 2),
                volume=round(vol, 2)
            ))
            current_price = close_p

        return candles

    def set_custom_fixture(self, symbol: str, candles: List[Candle]):
        """Injects a deterministic candle list for precise testing"""
        self._custom_fixtures[symbol] = candles

    def clear_custom_fixtures(self):
        self._custom_fixtures.clear()

    @staticmethod
    def generate_pattern_14_fixture(
        base_price: float = 1.08500,
        start_ts: int = 1700000000,
        tf_sec: int = 60,
        support_break_type: str = "close_below"
    ) -> List[Candle]:
        """
        Generates an exact Pattern Type 14 sequence fixture:
        1. Context / Bearish candle(s)
        2. First 2 Bullish candles forming a base / support level
        3. Support level is created at the swing low of this base
        4. Bearish candle(s) develop
        5. Bearish candle breaks support level with close below
        6. Confirmed DOWN Signal trigger candle
        """
        candles: List[Candle] = []
        p = base_price

        # 0. 5 background context candles (slightly downtrending)
        for i in range(5):
            ts = start_ts + (i * tf_sec)
            op = p
            cl = op - 0.00020  # Bearish
            hi = op + 0.00008
            lo = cl - 0.00008
            candles.append(Candle(timestamp=ts, open=round(op, 5), high=round(hi, 5), low=round(lo, 5), close=round(cl, 5), volume=1000.0))
            p = cl

        # 1. Bearish Starting Candle (index 5)
        ts = start_ts + (5 * tf_sec)
        c_bear_start = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00010, 5),
            low=round(p - 0.00035, 5),
            close=round(p - 0.00030, 5),
            volume=1200.0
        )
        candles.append(c_bear_start)
        p = c_bear_start.close
        swing_support_low = c_bear_start.low  # Key support baseline

        # 2. First Bullish Candle (index 6)
        ts = start_ts + (6 * tf_sec)
        c_bull1 = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00045, 5),
            low=round(p - 0.00005, 5),
            close=round(p + 0.00040, 5),
            volume=1400.0
        )
        candles.append(c_bull1)
        p = c_bull1.close

        # 3. Second Bullish Candle (index 7) -> 2 Bullish Candles sequence complete!
        ts = start_ts + (7 * tf_sec)
        c_bull2 = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00050, 5),
            low=round(p - 0.00005, 5),
            close=round(p + 0.00045, 5),
            volume=1500.0
        )
        candles.append(c_bull2)
        p = c_bull2.close

        # 4. Bearish Candle pulling back towards support (index 8)
        ts = start_ts + (8 * tf_sec)
        c_bear_pullback = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00005, 5),
            low=round(p - 0.00040, 5),
            close=round(p - 0.00035, 5),
            volume=1300.0
        )
        candles.append(c_bear_pullback)
        p = c_bear_pullback.close

        # 5. Breakout / Breakdown Candle (index 9)
        # Explicitly tests support break with close below support_level
        ts = start_ts + (9 * tf_sec)
        if support_break_type == "close_below":
            c_break = Candle(
                timestamp=ts,
                open=round(p, 5),
                high=round(p + 0.00005, 5),
                low=round(swing_support_low - 0.00030, 5),
                close=round(swing_support_low - 0.00020, 5),  # Close is strictly below support
                volume=1800.0  # Above average confirming volume
            )
        elif support_break_type == "wick_only":
            c_break = Candle(
                timestamp=ts,
                open=round(p, 5),
                high=round(p + 0.00005, 5),
                low=round(swing_support_low - 0.00020, 5),  # Low broke
                close=round(swing_support_low + 0.00010, 5),  # But close stayed ABOVE support
                volume=1100.0
            )
        else:  # no_break
            c_break = Candle(
                timestamp=ts,
                open=round(p, 5),
                high=round(p + 0.00015, 5),
                low=round(swing_support_low + 0.00010, 5),
                close=round(swing_support_low + 0.00015, 5),
                volume=900.0
            )

        candles.append(c_break)
        return candles

    @staticmethod
    def generate_inverted_pattern_14_fixture(
        base_price: float = 1.08500,
        start_ts: int = 1700000000,
        tf_sec: int = 60,
        resistance_break_type: str = "close_above"
    ) -> List[Candle]:
        """
        Generates an exact Inverted Pattern Type 14 sequence fixture:
        1. Context candles (slightly uptrending)
        2. Bullish Starting Candle (index 5)
        3. First 2 Bearish base candles establishing resistance
        4. Resistance level created at swing high
        5. Bullish pullback candle
        6. Bullish breakout candle closing above resistance
        """
        candles: List[Candle] = []
        p = base_price

        # 0. 5 background context candles (uptrending)
        for i in range(5):
            ts = start_ts + (i * tf_sec)
            op = p
            cl = op + 0.00020
            hi = cl + 0.00008
            lo = op - 0.00008
            candles.append(Candle(timestamp=ts, open=round(op, 5), high=round(hi, 5), low=round(lo, 5), close=round(cl, 5), volume=1000.0))
            p = cl

        # 1. Bullish Starting Candle (index 5)
        ts = start_ts + (5 * tf_sec)
        c_bull_start = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00035, 5),
            low=round(p - 0.00010, 5),
            close=round(p + 0.00030, 5),
            volume=1200.0
        )
        candles.append(c_bull_start)
        p = c_bull_start.close
        swing_res_high = c_bull_start.high

        # 2. First Bearish Candle (index 6)
        ts = start_ts + (6 * tf_sec)
        c_bear1 = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00005, 5),
            low=round(p - 0.00045, 5),
            close=round(p - 0.00040, 5),
            volume=1400.0
        )
        candles.append(c_bear1)
        p = c_bear1.close

        # 3. Second Bearish Candle (index 7) -> 2 Bearish base candles complete
        ts = start_ts + (7 * tf_sec)
        c_bear2 = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00005, 5),
            low=round(p - 0.00050, 5),
            close=round(p - 0.00045, 5),
            volume=1500.0
        )
        candles.append(c_bear2)
        p = c_bear2.close

        # 4. Bullish Pullback Candle (index 8)
        ts = start_ts + (8 * tf_sec)
        c_bull_pullback = Candle(
            timestamp=ts,
            open=round(p, 5),
            high=round(p + 0.00040, 5),
            low=round(p - 0.00005, 5),
            close=round(p + 0.00035, 5),
            volume=1300.0
        )
        candles.append(c_bull_pullback)
        p = c_bull_pullback.close

        # 5. Breakout Candle (index 9)
        ts = start_ts + (9 * tf_sec)
        if resistance_break_type == "close_above":
            c_break = Candle(
                timestamp=ts,
                open=round(p, 5),
                high=round(swing_res_high + 0.00030, 5),
                low=round(p - 0.00005, 5),
                close=round(swing_res_high + 0.00020, 5),  # Close is strictly above resistance
                volume=1800.0
            )
        else:
            c_break = Candle(
                timestamp=ts,
                open=round(p, 5),
                high=round(swing_res_high + 0.00020, 5),
                low=round(p - 0.00005, 5),
                close=round(swing_res_high - 0.00010, 5),
                volume=1000.0
            )
        candles.append(c_break)
        return candles
