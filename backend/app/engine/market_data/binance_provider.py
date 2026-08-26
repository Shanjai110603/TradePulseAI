import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.engine.market_data.base import MarketDataProvider, Candle


class BinanceDataProvider(MarketDataProvider):
    """
    Public live/historical crypto provider using Binance Public REST API (no API key required).
    """

    BASE_URL = "https://api.binance.com/api/v3"

    TIMEFRAME_MAP = {
        "1M": "1m",
        "5M": "5m",
        "15M": "15m",
        "30M": "30m",
        "1H": "1h",
        "4H": "4h",
        "1D": "1d",
    }

    def get_provider_name(self) -> str:
        return "binance"

    def is_live(self) -> bool:
        return True

    def get_supported_timeframes(self) -> List[str]:
        return list(self.TIMEFRAME_MAP.keys())

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.replace("/", "").replace("-", "").upper()

    async def get_assets(self, market_id: str) -> List[Dict[str, Any]]:
        return [
            {"symbol": "BTC/USDT", "name": "Bitcoin / Tether", "precision": 2, "min_movement": 0.01},
            {"symbol": "ETH/USDT", "name": "Ethereum / Tether", "precision": 2, "min_movement": 0.01},
            {"symbol": "SOL/USDT", "name": "Solana / Tether", "precision": 2, "min_movement": 0.01},
            {"symbol": "BNB/USDT", "name": "Binance Coin / Tether", "precision": 2, "min_movement": 0.01},
            {"symbol": "XRP/USDT", "name": "Ripple / Tether", "precision": 4, "min_movement": 0.0001},
            {"symbol": "ADA/USDT", "name": "Cardano / Tether", "precision": 4, "min_movement": 0.0001},
        ]

    async def get_current_price(self, symbol: str) -> float:
        binance_symbol = self._normalize_symbol(symbol)
        url = f"{self.BASE_URL}/ticker/price"
        params = {"symbol": binance_symbol}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return float(data["price"])

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1M",
        limit: int = 100,
        end_time: Optional[datetime] = None
    ) -> List[Candle]:
        binance_symbol = self._normalize_symbol(symbol)
        interval = self.TIMEFRAME_MAP.get(timeframe, "1m")
        url = f"{self.BASE_URL}/klines"
        params: Dict[str, Any] = {
            "symbol": binance_symbol,
            "interval": interval,
            "limit": min(limit, 1000),
        }
        if end_time:
            params["endTime"] = int(end_time.timestamp() * 1000)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            raw_candles = resp.json()

        candles: List[Candle] = []
        for c in raw_candles:
            # Binance kline format:
            # 0: Open time (ms)
            # 1: Open, 2: High, 3: Low, 4: Close, 5: Volume
            candles.append(Candle(
                timestamp=int(c[0] // 1000),
                open=float(c[1]),
                high=float(c[2]),
                low=float(c[3]),
                close=float(c[4]),
                volume=float(c[5])
            ))
        return candles
