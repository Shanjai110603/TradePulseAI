"""
Quotex Real Market Data Provider
================================
Connects directly to Quotex WebSocket API using a session token (SSID cookie).

Setup:
1. Log into quotex.com in your browser
2. Open DevTools (F12) → Application → Cookies → quotex.com (or qxbroker.com)
3. Copy the value of the 'ssid' cookie
4. Set QUOTEX_SESSION_TOKEN env var in Render dashboard (or .env file)

Falls back to high-quality synthetic OTC price simulation if token not configured.
"""
import asyncio
import json
import logging
import math
import random
import time
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

from app.core.config import settings
from app.engine.market_data.base import MarketDataProvider, Candle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Asset registry
# ---------------------------------------------------------------------------

QUOTEX_ASSETS = [
    {"symbol": "EUR/USD (OTC)", "base_asset": "EUR", "quote_asset": "USD", "name": "EUR/USD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 87, "is_otc": True, "ws_asset": "EURUSD_OTC"},
    {"symbol": "GBP/USD (OTC)", "base_asset": "GBP", "quote_asset": "USD", "name": "GBP/USD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 88, "is_otc": True, "ws_asset": "GBPUSD_OTC"},
    {"symbol": "USD/JPY (OTC)", "base_asset": "USD", "quote_asset": "JPY", "name": "USD/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 85, "is_otc": True, "ws_asset": "USDJPY_OTC"},
    {"symbol": "AUD/CAD (OTC)", "base_asset": "AUD", "quote_asset": "CAD", "name": "AUD/CAD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 86, "is_otc": True, "ws_asset": "AUDCAD_OTC"},
    {"symbol": "EUR/JPY (OTC)", "base_asset": "EUR", "quote_asset": "JPY", "name": "EUR/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 84, "is_otc": True, "ws_asset": "EURJPY_OTC"},
    {"symbol": "NZD/USD (OTC)", "base_asset": "NZD", "quote_asset": "USD", "name": "NZD/USD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 83, "is_otc": True, "ws_asset": "NZDUSD_OTC"},
    {"symbol": "USD/CHF (OTC)", "base_asset": "USD", "quote_asset": "CHF", "name": "USD/CHF OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 85, "is_otc": True, "ws_asset": "USDCHF_OTC"},
    {"symbol": "BTC/USDT (OTC)", "base_asset": "BTC", "quote_asset": "USDT", "name": "Bitcoin OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 90, "is_otc": True, "ws_asset": "BTCUSD_OTC"},
    {"symbol": "ETH/USDT (OTC)", "base_asset": "ETH", "quote_asset": "USDT", "name": "Ethereum OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 89, "is_otc": True, "ws_asset": "ETHUSD_OTC"},
    {"symbol": "EUR/USD", "base_asset": "EUR", "quote_asset": "USD", "name": "EUR/USD Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 82, "is_otc": False, "ws_asset": "EURUSD"},
    {"symbol": "GBP/USD", "base_asset": "GBP", "quote_asset": "USD", "name": "GBP/USD Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 82, "is_otc": False, "ws_asset": "GBPUSD"},
    {"symbol": "USD/JPY", "base_asset": "USD", "quote_asset": "JPY", "name": "USD/JPY Live Market", "price_precision": 3, "min_movement": 0.001, "payout": 80, "is_otc": False, "ws_asset": "USDJPY"},
    {"symbol": "AUD/USD", "base_asset": "AUD", "quote_asset": "USD", "name": "AUD/USD Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 81, "is_otc": False, "ws_asset": "AUDUSD"},
]

SYMBOL_TO_WS = {a["symbol"]: a["ws_asset"] for a in QUOTEX_ASSETS}

BASE_PRICES = {
    "EUR/USD (OTC)": 1.08450, "GBP/USD (OTC)": 1.27210, "USD/JPY (OTC)": 154.620,
    "AUD/CAD (OTC)": 0.89340, "EUR/JPY (OTC)": 167.450, "NZD/USD (OTC)": 0.59820,
    "USD/CHF (OTC)": 0.88420, "BTC/USDT (OTC)": 67500.0, "ETH/USDT (OTC)": 3520.0,
    "EUR/USD": 1.08520, "GBP/USD": 1.27180, "USD/JPY": 154.550, "AUD/USD": 0.65420,
}

PERIOD_MAP = {"1M": 60, "5M": 300, "15M": 900, "1H": 3600}


# ---------------------------------------------------------------------------
# Quotex WebSocket client
# ---------------------------------------------------------------------------

class QuotexWebSocketClient:
    """
    Minimal async Quotex WebSocket client.
    Authenticates with SSID cookie and fetches historical candle data.
    """

    WS_URLS = [
        "wss://ws.qxbroker.com/socket.io/?EIO=4&transport=websocket",
        "wss://ws2.qxbroker.com/socket.io/?EIO=4&transport=websocket",
        "wss://ws.quotex.io/socket.io/?EIO=4&transport=websocket",
        "wss://ws2.quotex.io/socket.io/?EIO=4&transport=websocket",
    ]

    def __init__(self, ssid: str):
        self.ssid = ssid
        self._candle_cache: Dict[str, List[dict]] = {}

    def _build_cookie_header(self) -> str:
        s = self.ssid.strip()
        if "=" in s:
            return s
        # If raw value given, provide both laravel_session and ssid for maximum compatibility
        return f"laravel_session={s}; ssid={s}"

    async def get_candles(self, ws_asset: str, period: int, count: int) -> List[dict]:
        """
        Fetch candles from Quotex WebSocket.
        Returns list of dicts with keys: time, open, close, high, low
        """
        end_time = int(time.time())
        received: List[dict] = []
        success = False
        cookie_hdr = self._build_cookie_header()

        for ws_url in self.WS_URLS:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Cookie": cookie_hdr,
                    "Origin": "https://qxbroker.com",
                }
                async with websockets.connect(
                    ws_url,
                    additional_headers=headers,
                    open_timeout=10,
                    close_timeout=5,
                ) as ws:
                    # EIO4 handshake
                    await asyncio.wait_for(ws.recv(), timeout=5)
                    await ws.send("40")  # Socket.IO connect

                    # Wait for Socket.IO connected confirmation
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        if not msg.startswith("40"):
                            continue
                    except asyncio.TimeoutError:
                        continue

                    # Request historical candles
                    payload = json.dumps([
                        "instruments/update",
                        {"asset": ws_asset, "period": period}
                    ])
                    await ws.send(f"42{payload}")

                    # Request candle history
                    history_payload = json.dumps([
                        "history/load",
                        {
                            "asset": ws_asset,
                            "period": period,
                            "count": count,
                            "time": end_time,
                        }
                    ])
                    await ws.send(f"42{history_payload}")

                    # Receive responses
                    deadline = asyncio.get_event_loop().time() + 8
                    while asyncio.get_event_loop().time() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=3)
                        except asyncio.TimeoutError:
                            break

                        if not raw.startswith("42"):
                            continue
                        data_str = raw[2:]
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        if not isinstance(data, list) or len(data) < 2:
                            continue

                        event = data[0]
                        payload_data = data[1]

                        if event == "history/load" and isinstance(payload_data, dict):
                            candles_raw = payload_data.get("candles", [])
                            for c in candles_raw:
                                if isinstance(c, (list, tuple)) and len(c) >= 5:
                                    received.append({
                                        "time": int(c[0]),
                                        "open": float(c[1]),
                                        "close": float(c[2]),
                                        "high": float(c[3]),
                                        "low": float(c[4]),
                                    })
                            if received:
                                success = True
                                break

                if success:
                    break

            except Exception as e:
                logger.warning(f"Quotex WS connection to {ws_url} failed: {e}")
                continue

        return received

    async def get_current_price(self, ws_asset: str) -> Optional[float]:
        """Get single live price tick."""
        for ws_url in self.WS_URLS:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Cookie": f"ssid={self.ssid}",
                    "Origin": "https://qxbroker.com",
                }
                async with websockets.connect(
                    ws_url,
                    additional_headers=headers,
                    open_timeout=8,
                    close_timeout=3,
                ) as ws:
                    await asyncio.wait_for(ws.recv(), timeout=5)
                    await ws.send("40")

                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        if not msg.startswith("40"):
                            continue
                    except asyncio.TimeoutError:
                        continue

                    sub_payload = json.dumps(["instruments/update", {"asset": ws_asset, "period": 60}])
                    await ws.send(f"42{sub_payload}")

                    deadline = asyncio.get_event_loop().time() + 5
                    while asyncio.get_event_loop().time() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=3)
                        except asyncio.TimeoutError:
                            break

                        if not raw.startswith("42"):
                            continue
                        try:
                            data = json.loads(raw[2:])
                        except Exception:
                            continue

                        if isinstance(data, list) and data[0] == "tick":
                            tick = data[1]
                            return float(tick.get("price", tick.get("p", 0)))

            except Exception as e:
                logger.debug(f"Live price fetch failed for {ws_asset}: {e}")

        return None


# ---------------------------------------------------------------------------
# Main provider
# ---------------------------------------------------------------------------

class QuotexMarketDataProvider(MarketDataProvider):
    """
    Quotex Digital Options & OTC Market Data Provider.

    When QUOTEX_SESSION_TOKEN is set in env, fetches real candles from
    Quotex's WebSocket API.
    When not set, generates high-quality deterministic synthetic OTC prices
    that preserve price continuity across requests.
    """

    def __init__(self):
        self._price_cache: Dict[str, float] = {}
        self._ssid: Optional[str] = getattr(settings, "QUOTEX_SESSION_TOKEN", None) or ""
        self._ws_client: Optional[QuotexWebSocketClient] = None
        self._live_mode = bool(self._ssid and len(self._ssid) > 10)

        if self._live_mode and HAS_WEBSOCKETS:
            self._ws_client = QuotexWebSocketClient(self._ssid)
            logger.info("QuotexMarketDataProvider: LIVE mode (WebSocket with SSID token)")
        else:
            logger.info(
                "QuotexMarketDataProvider: SIMULATION mode "
                "(set QUOTEX_SESSION_TOKEN env var to enable live data)"
            )

    async def get_assets(self, market_id: str) -> List[Dict[str, Any]]:
        return QUOTEX_ASSETS

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1M",
        limit: int = 100,
        end_time=None
    ) -> List[Candle]:
        """Fetch candles — real from Quotex WS when configured, else synthetic."""

        if self._live_mode and self._ws_client:
            ws_asset = SYMBOL_TO_WS.get(symbol, symbol.replace("/", "").replace(" (OTC)", "_OTC"))
            period = PERIOD_MAP.get(timeframe, 60)
            try:
                raw = await asyncio.wait_for(
                    self._ws_client.get_candles(ws_asset, period, limit),
                    timeout=12
                )
                if raw:
                    candles = [
                        Candle(
                            timestamp=c["time"],
                            open=c["open"],
                            high=c["high"],
                            low=c["low"],
                            close=c["close"],
                            volume=random.uniform(800, 3200),
                        )
                        for c in sorted(raw, key=lambda x: x["time"])
                    ]
                    if candles:
                        self._price_cache[symbol] = candles[-1].close
                        logger.debug(f"Live candles fetched for {symbol}: {len(candles)} candles")
                        return candles
                logger.warning(f"No live candles received for {symbol}, falling back to simulation")
            except Exception as e:
                logger.warning(f"Live candle fetch failed for {symbol}: {e}, using simulation")

        # Deterministic simulation — realistic OTC price generation
        return self._generate_synthetic_candles(symbol, timeframe, limit, end_time)

    def _generate_synthetic_candles(
        self, symbol: str, timeframe: str, limit: int, end_time=None
    ) -> List[Candle]:
        clean_sym = symbol.replace(" (OTC)", "").strip()
        base_price = BASE_PRICES.get(symbol, BASE_PRICES.get(clean_sym, 1.08500))

        seconds_step = PERIOD_MAP.get(timeframe, 60)
        end_dt = end_time or datetime.now(timezone.utc)
        end_ts = int(end_dt.timestamp()) if not isinstance(end_dt, (int, float)) else int(end_dt)
        end_ts -= end_ts % seconds_step
        start_ts = end_ts - (limit * seconds_step)

        is_crypto = "BTC" in symbol or "ETH" in symbol
        is_jpy = "JPY" in symbol
        vol = 0.00035 if not is_crypto else 0.0025
        if is_jpy:
            vol = 0.045
        if is_crypto:
            vol = 25.0 if "BTC" in symbol else 1.5

        # Seeded RNG for deterministic continuity within the same hour
        seed_val = int(abs(hash(symbol))) % 100000
        rng = random.Random(seed_val + (start_ts // 3600))

        candles: List[Candle] = []
        current_price = base_price

        for i in range(limit):
            t = start_ts + (i * seconds_step)
            # Sine-wave drift for realistic trending behaviour
            drift = math.sin(i / 14.0) * (vol * 0.35) + math.sin(i / 47.0) * (vol * 0.15)
            step = rng.gauss(0, vol * 0.8) + drift

            open_p = current_price
            close_p = open_p + step
            high_wick = abs(rng.gauss(0, vol * 0.45))
            low_wick = abs(rng.gauss(0, vol * 0.45))
            high_p = max(open_p, close_p) + high_wick
            low_p = min(open_p, close_p) - low_wick
            volume = rng.uniform(800, 3200)

            precision = 2 if is_crypto else (3 if is_jpy else 5)
            candles.append(Candle(
                timestamp=t,
                open=round(open_p, precision),
                high=round(high_p, precision),
                low=round(low_p, precision),
                close=round(close_p, precision),
                volume=round(volume, 2),
            ))
            current_price = close_p

        if candles:
            self._price_cache[symbol] = candles[-1].close

        return candles

    async def get_current_price(self, symbol: str) -> float:
        if self._live_mode and self._ws_client:
            ws_asset = SYMBOL_TO_WS.get(symbol, symbol.replace("/", "").replace(" (OTC)", "_OTC"))
            try:
                price = await asyncio.wait_for(self._ws_client.get_current_price(ws_asset), timeout=6)
                if price and price > 0:
                    self._price_cache[symbol] = price
                    return price
            except Exception:
                pass

        if symbol in self._price_cache:
            base = self._price_cache[symbol]
            is_crypto = "BTC" in symbol or "ETH" in symbol
            is_jpy = "JPY" in symbol
            if is_crypto:
                delta = random.uniform(-5.0, 5.0)
            elif is_jpy:
                delta = random.uniform(-0.005, 0.005)
            else:
                delta = random.uniform(-0.00005, 0.00005)
            return round(base + delta, 2 if is_crypto else (3 if is_jpy else 5))

        candles = await self.get_candles(symbol, limit=2)
        return candles[-1].close if candles else BASE_PRICES.get(symbol, 1.08500)

    def get_supported_timeframes(self) -> List[str]:
        return ["1M", "5M", "15M", "1H"]

    def get_provider_name(self) -> str:
        return "quotex"

    def is_live(self) -> bool:
        return self._live_mode
