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

import httpx

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
    # Forex OTC Pairs
    {"symbol": "EUR/USD (OTC)", "base_asset": "EUR", "quote_asset": "USD", "name": "EUR/USD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 87, "is_otc": True, "ws_asset": "EURUSD_otc"},
    {"symbol": "GBP/USD (OTC)", "base_asset": "GBP", "quote_asset": "USD", "name": "GBP/USD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 88, "is_otc": True, "ws_asset": "GBPUSD_otc"},
    {"symbol": "USD/JPY (OTC)", "base_asset": "USD", "quote_asset": "JPY", "name": "USD/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 85, "is_otc": True, "ws_asset": "USDJPY_otc"},
    {"symbol": "USD/CHF (OTC)", "base_asset": "USD", "quote_asset": "CHF", "name": "USD/CHF OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 85, "is_otc": True, "ws_asset": "USDCHF_otc"},
    {"symbol": "AUD/USD (OTC)", "base_asset": "AUD", "quote_asset": "USD", "name": "AUD/USD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 85, "is_otc": True, "ws_asset": "AUDUSD_otc"},
    {"symbol": "USD/CAD (OTC)", "base_asset": "USD", "quote_asset": "CAD", "name": "USD/CAD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 84, "is_otc": True, "ws_asset": "USDCAD_otc"},
    {"symbol": "NZD/USD (OTC)", "base_asset": "NZD", "quote_asset": "USD", "name": "NZD/USD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 83, "is_otc": True, "ws_asset": "NZDUSD_otc"},
    {"symbol": "EUR/GBP (OTC)", "base_asset": "EUR", "quote_asset": "GBP", "name": "EUR/GBP OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 86, "is_otc": True, "ws_asset": "EURGBP_otc"},
    {"symbol": "EUR/JPY (OTC)", "base_asset": "EUR", "quote_asset": "JPY", "name": "EUR/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 84, "is_otc": True, "ws_asset": "EURJPY_otc"},
    {"symbol": "GBP/JPY (OTC)", "base_asset": "GBP", "quote_asset": "JPY", "name": "GBP/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 87, "is_otc": True, "ws_asset": "GBPJPY_otc"},
    {"symbol": "AUD/CAD (OTC)", "base_asset": "AUD", "quote_asset": "CAD", "name": "AUD/CAD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 86, "is_otc": True, "ws_asset": "AUDCAD_otc"},
    {"symbol": "AUD/JPY (OTC)", "base_asset": "AUD", "quote_asset": "JPY", "name": "AUD/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 84, "is_otc": True, "ws_asset": "AUDJPY_otc"},
    {"symbol": "CAD/JPY (OTC)", "base_asset": "CAD", "quote_asset": "JPY", "name": "CAD/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 83, "is_otc": True, "ws_asset": "CADJPY_otc"},
    {"symbol": "CHF/JPY (OTC)", "base_asset": "CHF", "quote_asset": "JPY", "name": "CHF/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 85, "is_otc": True, "ws_asset": "CHFJPY_otc"},
    {"symbol": "EUR/AUD (OTC)", "base_asset": "EUR", "quote_asset": "AUD", "name": "EUR/AUD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 85, "is_otc": True, "ws_asset": "EURAUD_otc"},
    {"symbol": "EUR/CAD (OTC)", "base_asset": "EUR", "quote_asset": "CAD", "name": "EUR/CAD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 84, "is_otc": True, "ws_asset": "EURCAD_otc"},
    {"symbol": "EUR/CHF (OTC)", "base_asset": "EUR", "quote_asset": "CHF", "name": "EUR/CHF OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 84, "is_otc": True, "ws_asset": "EURCHF_otc"},
    {"symbol": "GBP/AUD (OTC)", "base_asset": "GBP", "quote_asset": "AUD", "name": "GBP/AUD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 86, "is_otc": True, "ws_asset": "GBPAUD_otc"},
    {"symbol": "GBP/CAD (OTC)", "base_asset": "GBP", "quote_asset": "CAD", "name": "GBP/CAD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 85, "is_otc": True, "ws_asset": "GBPCAD_otc"},
    {"symbol": "GBP/CHF (OTC)", "base_asset": "GBP", "quote_asset": "CHF", "name": "GBP/CHF OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 85, "is_otc": True, "ws_asset": "GBPCHF_otc"},
    {"symbol": "NZD/JPY (OTC)", "base_asset": "NZD", "quote_asset": "JPY", "name": "NZD/JPY OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 83, "is_otc": True, "ws_asset": "NZDJPY_otc"},
    {"symbol": "NZD/CAD (OTC)", "base_asset": "NZD", "quote_asset": "CAD", "name": "NZD/CAD OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 82, "is_otc": True, "ws_asset": "NZDCAD_otc"},
    {"symbol": "USD/INR (OTC)", "base_asset": "USD", "quote_asset": "INR", "name": "USD/INR OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 88, "is_otc": True, "ws_asset": "USDINR_otc"},
    {"symbol": "USD/BRL (OTC)", "base_asset": "USD", "quote_asset": "BRL", "name": "USD/BRL OTC (Quotex)", "price_precision": 4, "min_movement": 0.0001, "payout": 87, "is_otc": True, "ws_asset": "USDBRL_otc"},
    {"symbol": "USD/TRY (OTC)", "base_asset": "USD", "quote_asset": "TRY", "name": "USD/TRY OTC (Quotex)", "price_precision": 4, "min_movement": 0.0001, "payout": 86, "is_otc": True, "ws_asset": "USDTRY_otc"},
    {"symbol": "USD/MXN (OTC)", "base_asset": "USD", "quote_asset": "MXN", "name": "USD/MXN OTC (Quotex)", "price_precision": 4, "min_movement": 0.0001, "payout": 85, "is_otc": True, "ws_asset": "USDMXN_otc"},

    # Crypto Pairs
    {"symbol": "BTC/USDT (OTC)", "base_asset": "BTC", "quote_asset": "USDT", "name": "Bitcoin OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 90, "is_otc": True, "ws_asset": "BTCUSD_otc"},
    {"symbol": "ETH/USDT (OTC)", "base_asset": "ETH", "quote_asset": "USDT", "name": "Ethereum OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 89, "is_otc": True, "ws_asset": "ETHUSD_otc"},
    {"symbol": "LTC/USDT (OTC)", "base_asset": "LTC", "quote_asset": "USDT", "name": "Litecoin OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 88, "is_otc": True, "ws_asset": "LTCUSD_otc"},
    {"symbol": "XRP/USDT (OTC)", "base_asset": "XRP", "quote_asset": "USDT", "name": "Ripple OTC (Quotex)", "price_precision": 4, "min_movement": 0.0001, "payout": 87, "is_otc": True, "ws_asset": "XRPUSD_otc"},
    {"symbol": "SOL/USDT (OTC)", "base_asset": "SOL", "quote_asset": "USDT", "name": "Solana OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 88, "is_otc": True, "ws_asset": "SOLUSD_otc"},
    {"symbol": "DOGE/USDT (OTC)", "base_asset": "DOGE", "quote_asset": "USDT", "name": "Dogecoin OTC (Quotex)", "price_precision": 5, "min_movement": 0.00001, "payout": 86, "is_otc": True, "ws_asset": "DOGEUSD_otc"},

    # Commodities OTC
    {"symbol": "GOLD (OTC)", "base_asset": "XAU", "quote_asset": "USD", "name": "Gold OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 90, "is_otc": True, "ws_asset": "XAUUSD_otc"},
    {"symbol": "SILVER (OTC)", "base_asset": "XAG", "quote_asset": "USD", "name": "Silver OTC (Quotex)", "price_precision": 3, "min_movement": 0.001, "payout": 87, "is_otc": True, "ws_asset": "XAGUSD_otc"},
    {"symbol": "US CRUDE (OTC)", "base_asset": "OIL", "quote_asset": "USD", "name": "US Crude OTC (Quotex)", "price_precision": 2, "min_movement": 0.01, "payout": 86, "is_otc": True, "ws_asset": "UKBrent_otc"},

    # Live Standard Forex Market
    {"symbol": "EUR/USD", "base_asset": "EUR", "quote_asset": "USD", "name": "EUR/USD Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 82, "is_otc": False, "ws_asset": "EURUSD"},
    {"symbol": "GBP/USD", "base_asset": "GBP", "quote_asset": "USD", "name": "GBP/USD Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 82, "is_otc": False, "ws_asset": "GBPUSD"},
    {"symbol": "USD/JPY", "base_asset": "USD", "quote_asset": "JPY", "name": "USD/JPY Live Market", "price_precision": 3, "min_movement": 0.001, "payout": 80, "is_otc": False, "ws_asset": "USDJPY"},
    {"symbol": "AUD/USD", "base_asset": "AUD", "quote_asset": "USD", "name": "AUD/USD Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 81, "is_otc": False, "ws_asset": "AUDUSD"},
    {"symbol": "USD/CAD", "base_asset": "USD", "quote_asset": "CAD", "name": "USD/CAD Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 80, "is_otc": False, "ws_asset": "USDCAD"},
    {"symbol": "USD/CHF", "base_asset": "USD", "quote_asset": "CHF", "name": "USD/CHF Live Market", "price_precision": 5, "min_movement": 0.00001, "payout": 80, "is_otc": False, "ws_asset": "USDCHF"},
    {"symbol": "EUR/JPY", "base_asset": "EUR", "quote_asset": "JPY", "name": "EUR/JPY Live Market", "price_precision": 3, "min_movement": 0.001, "payout": 81, "is_otc": False, "ws_asset": "EURJPY"},
    {"symbol": "GBP/JPY", "base_asset": "GBP", "quote_asset": "JPY", "name": "GBP/JPY Live Market", "price_precision": 3, "min_movement": 0.001, "payout": 82, "is_otc": False, "ws_asset": "GBPJPY"},
]

SYMBOL_TO_WS = {a["symbol"]: a["ws_asset"] for a in QUOTEX_ASSETS}

BASE_PRICES = {
    "EUR/USD (OTC)": 1.08450, "GBP/USD (OTC)": 1.27210, "USD/JPY (OTC)": 154.620,
    "USD/CHF (OTC)": 0.88420, "AUD/USD (OTC)": 0.65480, "USD/CAD (OTC)": 1.36850,
    "NZD/USD (OTC)": 0.59820, "EUR/GBP (OTC)": 0.85240, "EUR/JPY (OTC)": 167.450,
    "GBP/JPY (OTC)": 196.520, "AUD/CAD (OTC)": 0.89340, "AUD/JPY (OTC)": 101.240,
    "CAD/JPY (OTC)": 113.120, "CHF/JPY (OTC)": 174.850, "EUR/AUD (OTC)": 1.65600,
    "EUR/CAD (OTC)": 1.48420, "EUR/CHF (OTC)": 0.95880, "GBP/AUD (OTC)": 1.94250,
    "GBP/CAD (OTC)": 1.74100, "GBP/CHF (OTC)": 1.12480, "NZD/JPY (OTC)": 95.039,
    "NZD/CAD (OTC)": 0.82410, "USD/INR (OTC)": 83.920, "USD/BRL (OTC)": 0.20184,
    "EUR/NZD (OTC)": 2.00411, "USD/ARS (OTC)": 1620.37, "USD/TRY (OTC)": 32.8450, "USD/MXN (OTC)": 18.2540,
    "USD/EGP (OTC)": 48.550, "USD/IDR (OTC)": 15820.0, "USD/PHP (OTC)": 56.420,
    "BTC/USDT (OTC)": 67500.0, "ETH/USDT (OTC)": 3520.0, "LTC/USDT (OTC)": 84.50,
    "XRP/USDT (OTC)": 0.5840, "SOL/USDT (OTC)": 154.20, "DOGE/USDT (OTC)": 0.12450,
    "GOLD (OTC)": 2412.50, "SILVER (OTC)": 29.450, "US CRUDE (OTC)": 78.40,
    "EUR/USD": 1.08520, "GBP/USD": 1.27180, "USD/JPY": 154.550, "AUD/USD": 0.65420,
    "USD/CAD": 1.36800, "USD/CHF": 0.88400, "EUR/JPY": 167.400, "GBP/JPY": 196.450,
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
        self._cooldown_until = 0.0

    def _build_cookie_header(self) -> str:
        import urllib.parse
        raw = urllib.parse.unquote(self.ssid.strip())
        if raw.startswith("ssid=") or raw.startswith("laravel_session="):
            return raw
        return f"ssid={raw}; laravel_session={raw}"

    async def get_candles(self, ws_asset: str, period: int, count: int) -> List[dict]:
        """
        Fetch candles from Quotex WebSocket.
        Returns list of dicts with keys: time, open, close, high, low
        """
        if time.time() < self._cooldown_until:
            return []

        import urllib.parse
        end_time = int(time.time())
        received: List[dict] = []
        success = False
        cookie_hdr = self._build_cookie_header()

        # Extract pure session token value for authorization payload
        raw_token = urllib.parse.unquote(self.ssid.strip())
        if "ssid=" in raw_token:
            for item in raw_token.split(";"):
                if "ssid=" in item:
                    raw_token = item.split("ssid=")[-1].strip()
                    break
        elif "laravel_session=" in raw_token:
            for item in raw_token.split(";"):
                if "laravel_session=" in item:
                    raw_token = item.split("laravel_session=")[-1].strip()
                    break

        for ws_url in self.WS_URLS:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
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

                    # Send Socket.IO authorization packet
                    auth_payload = json.dumps(["authorization", {"session": raw_token, "isDemo": 1}])
                    await ws.send(f"42{auth_payload}")

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

                    # Receive responses with ping/pong heartbeat
                    deadline = asyncio.get_event_loop().time() + 8
                    while asyncio.get_event_loop().time() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=3)
                        except asyncio.TimeoutError:
                            break

                        # Handle Socket.IO ping
                        if raw == "2":
                            await ws.send("3")  # pong
                            continue

                        if not raw.startswith("42"):
                            continue
                        data_str = raw[2:]
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        if not isinstance(data, list) or len(data) < 1:
                            continue

                        event = str(data[0])
                        if event == "authorization/reject":
                            logger.warning("[QUOTEX_WS] Quotex session token rejected by broker. Token is expired or invalid.")
                            break

                        if len(data) < 2:
                            continue
                        payload_data = data[1]

                        if "history" in event or "candle" in event or event == "instruments/update":
                            candles_raw = []
                            if isinstance(payload_data, dict):
                                candles_raw = payload_data.get("candles", payload_data.get("data", payload_data.get("history", [])))
                            elif isinstance(payload_data, list):
                                candles_raw = payload_data

                            for c in candles_raw:
                                if isinstance(c, (list, tuple)) and len(c) >= 5:
                                    received.append({
                                        "time": int(c[0]),
                                        "open": float(c[1]),
                                        "close": float(c[2]),
                                        "high": float(c[3]),
                                        "low": float(c[4]),
                                    })
                                elif isinstance(c, dict) and "time" in c:
                                    received.append({
                                        "time": int(c.get("time", c.get("t", 0))),
                                        "open": float(c.get("open", c.get("o", 0))),
                                        "close": float(c.get("close", c.get("c", 0))),
                                        "high": float(c.get("high", c.get("h", c.get("max", 0)))),
                                        "low": float(c.get("low", c.get("l", c.get("min", 0)))),
                                    })

                            if received:
                                success = True
                                break

                if success:
                    break

            except Exception as e:
                logger.debug(f"Quotex WS connection to {ws_url} failed: {e}")
                self._cooldown_until = time.time() + 30  # 30-sec cooldown on connection error
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
        if not self._ssid or len(self._ssid) < 5:
            try:
                for path in ["uploads/quotex_session.json", "backend/uploads/quotex_session.json", "/app/uploads/quotex_session.json"]:
                    if os.path.exists(path):
                        with open(path, "r") as f:
                            data = json.load(f)
                            cached_t = data.get("token")
                            if cached_t and len(cached_t) > 5:
                                self._ssid = cached_t
                                break
            except Exception:
                pass

        self._email: Optional[str] = getattr(settings, "QUOTEX_EMAIL", None) or ""
        self._password: Optional[str] = getattr(settings, "QUOTEX_PASSWORD", None) or ""
        self._ws_client: Optional[QuotexWebSocketClient] = None
        self._live_mode = bool(self._ssid and len(self._ssid) > 10)
        self._login_attempted = False
        self._ingested_candles: Dict[str, List[Candle]] = {}
        self._last_ingest_ts: Dict[str, float] = {}

    def ingest_candles(self, symbol: str, timeframe: str, raw_candles: List[Dict[str, Any]]) -> int:
        """Stores real live external candles streamed from an online cloud relay or provider."""
        converted = []
        for c in raw_candles:
            ts = int(c.get("time", c.get("timestamp", time.time())))
            converted.append(Candle(
                timestamp=ts,
                open=float(c["open"]),
                high=float(c["high"]),
                low=float(c["low"]),
                close=float(c["close"]),
                volume=float(c.get("volume", 1200.0)),
                is_closed=c.get("is_closed", True)
            ))
        if converted:
            converted.sort(key=lambda x: x.timestamp)
            key = f"{symbol}_{timeframe}"
            self._ingested_candles[key] = converted[-100:]
            self._last_ingest_ts[key] = time.time()
            self._price_cache[symbol] = converted[-1].close
            return len(converted)
        return 0

    async def ensure_live_connection(self):
        """Ensures active live connection to Quotex WebSocket"""
        if self._live_mode and self._ws_client:
            return True

        if not self._ssid and self._email and self._password and not self._login_attempted:
            self._login_attempted = True
            try:
                from app.engine.market_data.session_renewer import QuotexSessionRenewer
                token = await QuotexSessionRenewer.get_session_cookies(self._email, self._password)
                if token:
                    self._ssid = token
                    self._live_mode = True
                    self._ws_client = QuotexWebSocketClient(token)
                    logger.info("[QUOTEX_PROVIDER] Initialized live Quotex WebSocket client with auto-renewed token.")
                    return True
            except Exception as e:
                logger.debug(f"[QUOTEX_PROVIDER] Auto-login attempt notice: {e}")

        if self._ssid and not self._ws_client:
            self._ws_client = QuotexWebSocketClient(self._ssid)
            self._live_mode = True
            return True

    def set_live_session(self, token: str):
        """Dynamically injects a fresh live Quotex session SSID cookie without restarting server."""
        raw_token = token.strip()
        self._ssid = raw_token
        self._live_mode = True
        self._ws_client = QuotexWebSocketClient(raw_token)
        self._login_attempted = False
        logger.info(f"[QUOTEX_PROVIDER] Live session injected dynamically (length={len(raw_token)}). Live mode active.")

    async def get_assets(self, market_id: str) -> List[Dict[str, Any]]:
        return QUOTEX_ASSETS

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "1M",
        limit: int = 100,
        end_time=None,
        strict_live_only: bool = True
    ) -> List[Candle]:
        """Fetch candles — real from Ingestion Relay or Quotex WS. Returns empty if live data unavailable."""
        await self.ensure_live_connection()
        # 1. Check if we have freshly ingested real candles from cloud relay (within last 180s)
        cache_key = f"{symbol}_{timeframe}"
        if cache_key in self._ingested_candles:
            last_ts = self._last_ingest_ts.get(cache_key, 0.0)
            if (time.time() - last_ts) < 180:
                candles = self._ingested_candles[cache_key][-limit:]
                if candles and len(candles) >= 5:
                    self._price_cache[symbol] = candles[-1].close
                    return candles

        # 2. Check if direct live WebSocket client has candles
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
                            volume=float(c.get("volume", 1200)),
                        )
                        for c in sorted(raw, key=lambda x: x["time"])
                    ]
                    if candles:
                        self._price_cache[symbol] = candles[-1].close
                        return candles
            except Exception:
                pass

        # Strict Live Mode: Do NOT generate fake/synthetic candles
        if strict_live_only:
            return []

        # Only for offline test suites when explicitly requested (strict_live_only=False)
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
        vol = 0.00025 if not is_crypto else 0.0020
        if is_jpy:
            vol = 0.035
        if is_crypto:
            vol = 18.0 if "BTC" in symbol else 1.2
        precision = 2 if is_crypto else (3 if is_jpy else 5)

        seed_base = int(abs(hash(symbol))) % 100000
        start_index = start_ts // seconds_step

        # Pre-walk starting price stably from epoch index
        running_price = base_price
        for idx in range(start_index - 30, start_index):
            r = random.Random(seed_base ^ (idx * 31))
            drift = math.sin(idx / 18.0) * (vol * 0.3)
            running_price += r.gauss(0, vol * 0.5) + drift

        candles: List[Candle] = []
        for i in range(limit):
            t = start_ts + (i * seconds_step)
            idx = t // seconds_step
            r = random.Random(seed_base ^ (idx * 31))

            drift = math.sin(idx / 18.0) * (vol * 0.3) + math.sin(idx / 53.0) * (vol * 0.15)
            step = r.gauss(0, vol * 0.5) + drift

            open_p = running_price
            close_p = open_p + step

            # If current active forming candle, inject smooth live tick pulse
            if i == limit - 1:
                cur_sec = time.time()
                live_tick = math.sin(cur_sec * 1.5) * (vol * 0.35)
                close_p = open_p + live_tick

            high_wick = abs(r.gauss(0, vol * 0.3))
            low_wick = abs(r.gauss(0, vol * 0.3))
            high_p = max(open_p, close_p) + high_wick
            low_p = min(open_p, close_p) - low_wick

            candles.append(Candle(
                timestamp=t,
                open=round(open_p, precision),
                high=round(high_p, precision),
                low=round(low_p, precision),
                close=round(close_p, precision),
                volume=round(r.uniform(900, 2800), 2),
            ))
            running_price = open_p + step

        if candles:
            self._price_cache[symbol] = candles[-1].close

        return candles

    async def get_current_price(self, symbol: str) -> float:
        await self.ensure_live_connection()
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
            return self._price_cache[symbol]

        cache_key = f"{symbol}_1M"
        if cache_key in self._ingested_candles and self._ingested_candles[cache_key]:
            return self._ingested_candles[cache_key][-1].close

        candles = await self.get_candles(symbol, limit=2, strict_live_only=True)
        return candles[-1].close if candles else BASE_PRICES.get(symbol, 1.08500)

    def get_supported_timeframes(self) -> List[str]:
        return ["1M", "5M", "15M", "1H"]

    def get_provider_name(self) -> str:
        return "quotex"

    def is_live(self) -> bool:
        return self._live_mode

    def compute_technical_snapshot(self, candles: List[Candle], current_price: Optional[float] = None) -> Dict[str, Any]:
        """Calculates a comprehensive technical snapshot dictionary from current candles"""
        if not candles:
            return {}
        from app.engine.indicators.engine import TechnicalIndicatorEngine
        snapshot = TechnicalIndicatorEngine.calculate_technical_snapshot(candles)
        if current_price and "market_structure" in snapshot:
            snapshot["market_structure"]["current_price"] = current_price
        return snapshot
