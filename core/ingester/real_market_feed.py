"""
TradePulse Real Market Open-Source Data Feed
Streams authentic live interbank quotes and 1-minute OHLCV candles for Real Market Forex,
Commodities, and Spot Crypto using free open-source endpoints (Yahoo Finance v8 & Binance WebSocket).
Zero API keys or paid subscriptions required.
"""
import asyncio
import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional
import httpx

from core.models.candle import Candle
from core.ingester.asset_registry import asset_registry

logger = logging.getLogger(__name__)

# Real Market Forex and Commodities ticker mappings (Yahoo Finance format)
REAL_MARKET_YAHOO_MAP: Dict[str, str] = {
    # Major & Minor Forex Pairs
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    "AUD/USD": "AUDUSD=X",
    "NZD/USD": "NZDUSD=X",
    "CAD/JPY": "CADJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "EUR/JPY": "EURJPY=X",
    "AUD/JPY": "AUDJPY=X",
    "CHF/JPY": "CHFJPY=X",
    "EUR/CHF": "EURCHF=X",
    "EUR/GBP": "EURGBP=X",
    "EUR/AUD": "EURAUD=X",
    "EUR/CAD": "EURCAD=X",
    "EUR/NZD": "EURNZD=X",
    "GBP/AUD": "GBPAUD=X",
    "GBP/CAD": "GBPCAD=X",
    "GBP/CHF": "GBPCHF=X",
    "GBP/NZD": "GBPNZD=X",
    "AUD/CAD": "AUDCAD=X",
    "AUD/CHF": "AUDCHF=X",
    "AUD/NZD": "AUDNZD=X",
    "CAD/CHF": "CADCHF=X",
    "NZD/CAD": "NZDCAD=X",
    "NZD/CHF": "NZDCHF=X",
    "NZD/JPY": "NZDJPY=X",

    # Commodities (Spot / Current Futures)
    "Gold": "GC=F",
    "Silver": "SI=F",

    # World Indices
    "S&P/ASX 200": "^AXJO",
    "FTSE 100": "^FTSE",
    "IBEX 35": "^IBEX",
    "Nikkei 225": "^N225",
    "EURO STOXX 50": "^STOXX50E",
    "CAC 40": "^FCHI",
    "Hong Kong 50": "^HSI",
    "FTSE China A50 Index": "FTSEChinaA50",
}

# Real Spot Crypto ticker mappings (Binance format)
BINANCE_CRYPTO_MAP: Dict[str, str] = {
    "BTC/USDT": "btcusdt",
    "ETH/USDT": "ethusdt",
    "SOL/USDT": "solusdt",
    "LTC/USDT": "ltcusdt",
    "XRP/USDT": "xrpusdt",
}


class RealMarketFeed:
    """
    Dedicated ingestion feed for Real Market Forex, Commodities, and Crypto.
    Runs asynchronously, bootstrapping historical 1-minute bars and streaming live ticks.
    """

    def __init__(
        self,
        candle_store=None,
        on_tick: Optional[Callable[[str, float, str], None]] = None,
        on_candle: Optional[Callable[[str, Candle], None]] = None
    ):
        self.store = candle_store
        self.on_tick = on_tick
        self.on_candle = on_candle
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._latest_prices: Dict[str, float] = {}
        self._last_candle_minute: Dict[str, int] = {}
        self._client: Optional[httpx.AsyncClient] = None

    def start(self):
        """Starts the background ingestion thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_thread, daemon=True, name="TradePulse-RealMarketFeed")
        self._thread.start()
        logger.info("[REAL MARKET FEED] Open-source Real Market data feed started.")

    def stop(self):
        """Stops the data feed."""
        self.running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("[REAL MARKET FEED] Open-source Real Market data feed stopped.")

    def _run_thread(self):
        """Thread worker initializing asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main_loop())

    async def _main_loop(self):
        """Main async orchestration loop for Real Market streams."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(headers=headers, timeout=6.0) as client:
            self._client = client

            # 1. Initial bootstrap of 1-minute historical candles for all real market pairs
            await self._bootstrap_all_history()

            # 2. Start Binance WebSocket task for real spot crypto
            binance_task = asyncio.create_task(self._run_binance_stream())

            # 3. Continuous high-frequency polling loop for Forex & Commodities
            poll_task = asyncio.create_task(self._run_forex_polling())

            await asyncio.gather(binance_task, poll_task, return_exceptions=True)

    async def _bootstrap_all_history(self):
        """Bootstraps authentic 1-minute historical candles for all Real Market pairs."""
        logger.info(f"[REAL MARKET FEED] Bootstrapping history for {len(REAL_MARKET_YAHOO_MAP)} pairs...")
        for symbol, ticker in REAL_MARKET_YAHOO_MAP.items():
            if not self.running:
                break
            try:
                candles = await self.fetch_history(symbol, ticker)
                if candles and self.store:
                    self.store.bootstrap_history(symbol, candles)
                    latest_price = candles[-1].close
                    self._dispatch_tick(symbol, latest_price, source="real_market")
                await asyncio.sleep(0.04)  # Smooth 40ms pacing
            except Exception as e:
                logger.debug(f"[REAL MARKET FEED] History bootstrap error for {symbol}: {e}")

    async def fetch_history(self, symbol: str, ticker: str) -> List[Candle]:
        """Fetches authentic 1-minute candles from Yahoo Finance v8 chart API."""
        if not self._client:
            return []
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
        try:
            resp = await self._client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            result = data.get("chart", {}).get("result")
            if not result or len(result) == 0:
                return []

            res = result[0]
            timestamps = res.get("timestamp", [])
            indicators = res.get("indicators", {}).get("quote", [{}])[0]
            opens = indicators.get("open", [])
            highs = indicators.get("high", [])
            lows = indicators.get("low", [])
            closes = indicators.get("close", [])
            volumes = indicators.get("volume", [])

            candles: List[Candle] = []
            for i, ts in enumerate(timestamps):
                if i >= len(opens) or i >= len(closes):
                    break
                o = opens[i]
                h = highs[i]
                l = lows[i]
                c = closes[i]
                v = volumes[i] if i < len(volumes) and volumes[i] is not None else 0.0
                if any(x is None for x in [o, h, l, c]):
                    continue
                candles.append(Candle(
                    timestamp=int(ts),
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=float(v)
                ))
            return candles
        except Exception as e:
            logger.debug(f"[REAL MARKET FEED] Chart API error for {ticker}: {e}")
            return []

    async def _run_forex_polling(self):
        """Paced high-frequency polling loop fetching live spot rates for Forex & Commodities."""
        symbols_list = list(REAL_MARKET_YAHOO_MAP.items())
        batch_size = 5
        idx = 0

        while self.running:
            try:
                # Poll a slice of symbols every cycle
                batch = symbols_list[idx : idx + batch_size]
                idx = (idx + batch_size) % len(symbols_list)

                tasks = [self._poll_symbol(sym, tick) for sym, tick in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

                await asyncio.sleep(0.4)  # 400ms between batches -> full cycle of 28 pairs every ~2.2s
            except Exception as e:
                logger.debug(f"[REAL MARKET FEED] Polling loop exception: {e}")
                await asyncio.sleep(1.0)

    async def _poll_symbol(self, symbol: str, ticker: str):
        """Fetches the latest live quote for a single symbol and detects 1m candle closure."""
        if not self._client or not self.running:
            return
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
        try:
            resp = await self._client.get(url)
            if resp.status_code != 200:
                return
            data = resp.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})
            price = meta.get("regularMarketPrice")
            if price is not None and float(price) > 0.0001:
                price_f = float(price)
                self._dispatch_tick(symbol, price_f, source="real_market")

                # Accumulate tick in CandleStore; emits completed bar on minute rollover
                if self.store:
                    now_ts = int(time.time())
                    completed_bar = self.store.add_tick(symbol, price_f, now_ts)
                    if completed_bar and self.on_candle:
                        try:
                            self.on_candle(symbol, completed_bar)
                        except Exception as ce:
                            logger.debug(f"[REAL MARKET FEED] on_candle error: {ce}")

        except Exception as e:
            logger.debug(f"[REAL MARKET FEED] Poll error for {symbol}: {e}")

    async def _run_binance_stream(self):
        """Connects to Binance public WebSocket stream for live real-time spot crypto."""
        import websockets
        stream_names = [f"{s}@trade/{s}@kline_1m" for s in BINANCE_CRYPTO_MAP.values()]
        url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(stream_names)}"

        while self.running:
            try:
                logger.info("[REAL MARKET FEED] Connecting to Binance public WebSocket stream...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("[REAL MARKET FEED] Connected to Binance Spot Crypto stream!")
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        stream = data.get("stream", "")
                        payload = data.get("data", {})

                        # Trade tick stream (sub-second tick updates)
                        if "@trade" in stream:
                            coin = payload.get("s", "").lower()
                            display_sym = next((k for k, v in BINANCE_CRYPTO_MAP.items() if v == coin), None)
                            price = payload.get("p")
                            if display_sym and price:
                                self._dispatch_tick(display_sym, float(price), source="binance_spot")

                        # 1-minute kline stream
                        elif "@kline" in stream:
                            kline = payload.get("k", {})
                            coin = payload.get("s", "").lower()
                            display_sym = next((k for k, v in BINANCE_CRYPTO_MAP.items() if v == coin), None)
                            is_closed = kline.get("x", False)
                            if display_sym and is_closed:
                                bar = Candle(
                                    timestamp=int(kline.get("t", 0) / 1000),
                                    open=float(kline.get("o", 0)),
                                    high=float(kline.get("h", 0)),
                                    low=float(kline.get("l", 0)),
                                    close=float(kline.get("c", 0)),
                                    volume=float(kline.get("v", 0))
                                )
                                if self.store:
                                    self.store.add_candle(display_sym, bar)
                                if self.on_candle:
                                    try:
                                        self.on_candle(display_sym, bar)
                                    except Exception as ce:
                                        logger.debug(f"[REAL MARKET FEED] on_candle error: {ce}")

            except Exception as e:
                logger.debug(f"[REAL MARKET FEED] Binance stream error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5.0)

    def _dispatch_tick(self, symbol: str, price: float, source: str = "real_market"):
        """Updates asset registry and dispatches tick callback."""
        self._latest_prices[symbol] = price
        asset_registry.update_latest_price(symbol, price, source=source)
        if self.on_tick:
            try:
                self.on_tick(symbol, price, source)
            except Exception as te:
                logger.debug(f"[REAL MARKET FEED] on_tick error: {te}")
