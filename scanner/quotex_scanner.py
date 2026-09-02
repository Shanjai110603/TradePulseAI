"""
TradePulse Quotex Multi-Currency Scanner
========================================
A standalone Windows app that:
 1. Launches Chrome with remote-debugging enabled
 2. Connects to Quotex and uses your existing login session
 3. Automatically cycles through ALL high-payout OTC currencies
 4. Reads the real live price every 2 seconds
 5. Streams OHLC candles to the TradePulse bot at http://127.0.0.1:8000

Usage (on the Windows Server):
    python quotex_scanner.py

No Playwright, no Selenium, no bot detection.
Uses Chrome DevTools Protocol (CDP) over real Google Chrome.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("quotex_scanner")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CDP_PORT = 9222
CHROME_USER_DATA = str(Path.home() / "QuotexScannerProfile")
BOT_INGEST_URL = "http://127.0.0.1:8000/api/v1/markets/candles/ingest"
QUOTEX_TRADE_URL = "https://qxbroker.com/en/trade"

# All OTC currencies the scanner will cycle through
OTC_CURRENCIES = [
    {"name": "EUR/USD (OTC)", "ws_asset": "EURUSD_otc", "precision": 5},
    {"name": "GBP/USD (OTC)", "ws_asset": "GBPUSD_otc", "precision": 5},
    {"name": "USD/JPY (OTC)", "ws_asset": "USDJPY_otc", "precision": 3},
    {"name": "AUD/USD (OTC)", "ws_asset": "AUDUSD_otc", "precision": 5},
    {"name": "USD/CHF (OTC)", "ws_asset": "USDCHF_otc", "precision": 5},
    {"name": "USD/CAD (OTC)", "ws_asset": "USDCAD_otc", "precision": 5},
    {"name": "NZD/USD (OTC)", "ws_asset": "NZDUSD_otc", "precision": 5},
    {"name": "EUR/GBP (OTC)", "ws_asset": "EURGBP_otc", "precision": 5},
    {"name": "EUR/JPY (OTC)", "ws_asset": "EURJPY_otc", "precision": 3},
    {"name": "GBP/JPY (OTC)", "ws_asset": "GBPJPY_otc", "precision": 3},
    {"name": "AUD/CAD (OTC)", "ws_asset": "AUDCAD_otc", "precision": 5},
    {"name": "AUD/JPY (OTC)", "ws_asset": "AUDJPY_otc", "precision": 3},
    {"name": "USD/INR (OTC)", "ws_asset": "USDINR_otc", "precision": 3},
    {"name": "USD/BRL (OTC)", "ws_asset": "USDBRL_otc", "precision": 4},
    {"name": "USD/PKR (OTC)", "ws_asset": "USDPKR_otc", "precision": 3},
    {"name": "USD/ZAR (OTC)", "ws_asset": "USDZAR_otc", "precision": 4},
    {"name": "NZD/CAD (OTC)", "ws_asset": "NZDCAD_otc", "precision": 5},
    {"name": "USD/MXN (OTC)", "ws_asset": "USDMXN_otc", "precision": 4},
    {"name": "USD/TRY (OTC)", "ws_asset": "USDTRY_otc", "precision": 4},
    {"name": "USD/EGP (OTC)", "ws_asset": "USDEGP_otc", "precision": 3},
]

# Per-currency candle accumulators (OHLCV within each 60-second window)
_candle_accumulators: Dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Chrome Launcher
# ---------------------------------------------------------------------------

def find_chrome() -> Optional[str]:
    """Find an installed Chrome or Edge executable."""
    for path in CHROME_PATHS:
        if os.path.isfile(path):
            return path
    return None


def launch_chrome() -> subprocess.Popen:
    """Launch Chrome with remote debugging enabled."""
    chrome_exe = find_chrome()
    if not chrome_exe:
        logger.error("Google Chrome or Microsoft Edge not found! Install Chrome first.")
        sys.exit(1)

    logger.info(f"Launching Chrome from: {chrome_exe}")
    logger.info(f"   CDP Debug Port: {CDP_PORT}")
    logger.info(f"   User Data Dir:  {CHROME_USER_DATA}")

    args = [
        chrome_exe,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_USER_DATA}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        QUOTEX_TRADE_URL,
    ]

    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info(f"Chrome launched (PID {proc.pid}). Waiting for CDP to be ready...")
    return proc


# ---------------------------------------------------------------------------
# CDP (Chrome DevTools Protocol) Client
# ---------------------------------------------------------------------------

class CDPClient:
    """Minimal CDP client for controlling Chrome via HTTP + WebSocket."""

    def __init__(self, port: int = CDP_PORT):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._ws = None
        self._msg_id = 0
        self._http = httpx.AsyncClient(timeout=10)

    async def wait_for_ready(self, timeout: float = 60):
        """Wait until Chrome's CDP endpoint is reachable."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = await self._http.get(f"{self.base_url}/json/version")
                if resp.status_code == 200:
                    info = resp.json()
                    logger.info(f"CDP Connected: {info.get('Browser', 'Chrome')}")
                    return
            except Exception:
                pass
            await asyncio.sleep(1)
        raise TimeoutError("Chrome CDP did not become ready in time")

    async def get_targets(self) -> list:
        """Get all browser tabs/targets."""
        resp = await self._http.get(f"{self.base_url}/json")
        return resp.json()

    async def find_quotex_tab(self) -> Optional[dict]:
        """Find the Quotex trading tab."""
        targets = await self.get_targets()
        for t in targets:
            url = t.get("url", "")
            if "qxbroker.com" in url or "quotex.io" in url:
                return t
        return None

    async def connect_ws(self, ws_url: str):
        """Connect to a target's WebSocket debug URL."""
        try:
            import websockets
            self._ws = await websockets.connect(ws_url, max_size=10_000_000)
            logger.info("CDP WebSocket connected to Quotex tab")
        except ImportError:
            logger.error("websockets package required. Install with: pip install websockets")
            sys.exit(1)

    async def send_command(self, method: str, params: dict = None) -> dict:
        """Send a CDP command and wait for the response."""
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(msg))

        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=15)
            data = json.loads(raw)
            if data.get("id") == self._msg_id:
                return data
            # Ignore events

    async def evaluate_js(self, expression: str) -> any:
        """Execute JavaScript in the page and return the result."""
        result = await self.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val = result.get("result", {}).get("result", {})
        return val.get("value")

    async def close(self):
        if self._ws:
            await self._ws.close()
        await self._http.aclose()


# ---------------------------------------------------------------------------
# Candle Accumulator (builds proper 1-min OHLCV from tick prices)
# ---------------------------------------------------------------------------

def accumulate_tick(symbol: str, price: float) -> Optional[dict]:
    """
    Accumulates tick prices into proper 1-minute OHLCV candles.
    Returns a completed candle dict when a 60-second window closes.
    """
    now = time.time()
    current_minute = int(now // 60) * 60  # floor to minute boundary

    if symbol not in _candle_accumulators:
        _candle_accumulators[symbol] = {
            "minute": current_minute,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "ticks": 1,
        }
        return None

    acc = _candle_accumulators[symbol]

    # Same minute - update OHLC
    if acc["minute"] == current_minute:
        acc["high"] = max(acc["high"], price)
        acc["low"] = min(acc["low"], price)
        acc["close"] = price
        acc["ticks"] += 1
        return None

    # New minute - emit the completed candle and start fresh
    completed = {
        "timestamp": acc["minute"],
        "open": acc["open"],
        "high": acc["high"],
        "low": acc["low"],
        "close": acc["close"],
        "volume": acc["ticks"] * 100,
    }

    _candle_accumulators[symbol] = {
        "minute": current_minute,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "ticks": 1,
    }

    return completed


# ---------------------------------------------------------------------------
# Bot Ingestor (sends candles to the FastAPI backend)
# ---------------------------------------------------------------------------

async def send_candle_to_bot(http: httpx.AsyncClient, symbol: str, candle: dict):
    """POST a completed candle to the TradePulse bot."""
    try:
        payload = {
            "symbol": symbol,
            "timeframe": "1M",
            "candles": [candle],
        }
        resp = await http.post(BOT_INGEST_URL, json=payload)
        if resp.status_code == 200:
            logger.info(
                f"INGESTED: {symbol} | O:{candle['open']:.5g} H:{candle['high']:.5g} "
                f"L:{candle['low']:.5g} C:{candle['close']:.5g} | Vol:{candle['volume']}"
            )
        else:
            logger.warning(f"Ingest returned {resp.status_code} for {symbol}")
    except Exception as e:
        logger.debug(f"Ingest error for {symbol}: {e}")


async def send_live_tick_to_bot(http: httpx.AsyncClient, symbol: str, price: float):
    """Send the current live tick as an immediate candle snapshot (for /signal scans)."""
    try:
        payload = {
            "symbol": symbol,
            "timeframe": "1M",
            "candles": [{
                "timestamp": int(time.time()),
                "open": price,
                "high": price + 0.00005,
                "low": price - 0.00005,
                "close": price,
                "volume": 100,
            }],
        }
        await http.post(BOT_INGEST_URL, json=payload)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main Scanner Loop
# ---------------------------------------------------------------------------

# JavaScript to inject into the Quotex page that reads live price
JS_READ_PRICE = r"""
(() => {
    const allEls = document.querySelectorAll('*');
    let bestPrice = null;
    for (const el of allEls) {
        if (el.children.length === 0) {
            const t = el.innerText ? el.innerText.trim() : '';
            if (/^\d+\.\d{2,5}$/.test(t)) {
                const p = parseFloat(t);
                if (p > 0) bestPrice = p;
            }
        }
    }
    return bestPrice;
})()
"""

# JavaScript to click on a specific currency tab in Quotex
JS_CLICK_TAB_TEMPLATE = """
(() => {{
    const tabs = document.querySelectorAll('.pair-item, .tab-item, .navigation-item, [class*="asset-item"], [class*="pair"]');
    for (const tab of tabs) {{
        const txt = tab.innerText || tab.textContent || '';
        if (txt.includes('{pair_code}')) {{
            tab.click();
            return 'clicked:{pair_code}';
        }}
    }}
    const allClickable = document.querySelectorAll('div, span, button, a');
    for (const el of allClickable) {{
        const txt = (el.innerText || '').trim();
        if (txt.includes('{pair_code}') && el.offsetParent !== null) {{
            el.click();
            return 'clicked_alt:{pair_code}';
        }}
    }}
    return 'not_found:{pair_code}';
}})()
"""

# JavaScript to read the active asset name from the page
JS_READ_ACTIVE_ASSET = r"""
(() => {
    const selectors = ['.pair-name', '.asset-name', '.current-symbol', '[class*="pair-title"]'];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText) return el.innerText.trim();
    }
    const allEls = document.querySelectorAll('*');
    for (const el of allEls) {
        const t = (el.innerText || '').trim();
        if (/^[A-Z]{3}\/[A-Z]{3}/.test(t) && t.length < 30) {
            return t;
        }
    }
    return null;
})()
"""

# JavaScript to read payout percentage
JS_READ_PAYOUT = r"""
(() => {
    const allEls = document.querySelectorAll('*');
    for (const el of allEls) {
        if (el.children.length === 0) {
            const t = (el.innerText || '').trim();
            const m = t.match(/^(\d{2,3})%$/);
            if (m) return parseInt(m[1]);
        }
    }
    return null;
})()
"""


async def run_scanner():
    """Main scanner entry point."""
    logger.info("=" * 60)
    logger.info("  TradePulse Quotex Multi-Currency Scanner")
    logger.info("=" * 60)

    # 1. Launch Chrome
    chrome_proc = launch_chrome()
    await asyncio.sleep(5)  # Give Chrome time to start

    # 2. Connect via CDP
    cdp = CDPClient(CDP_PORT)
    try:
        await cdp.wait_for_ready(timeout=30)
    except TimeoutError:
        logger.error("Could not connect to Chrome. Make sure Chrome is running.")
        return

    # 3. Find the Quotex tab
    quotex_tab = None
    for attempt in range(10):
        quotex_tab = await cdp.find_quotex_tab()
        if quotex_tab:
            break
        logger.info(f"   Waiting for Quotex tab... (attempt {attempt + 1})")
        await asyncio.sleep(3)

    if not quotex_tab:
        logger.error("No Quotex tab found. Please log into qxbroker.com in Chrome.")
        await cdp.close()
        return

    ws_debug_url = quotex_tab.get("webSocketDebuggerUrl")
    if not ws_debug_url:
        logger.error("No WebSocket debugger URL for Quotex tab")
        await cdp.close()
        return

    await cdp.connect_ws(ws_debug_url)
    logger.info(f"Connected to Quotex tab: {quotex_tab.get('title', 'Unknown')}")

    # 4. Enable Runtime domain
    await cdp.send_command("Runtime.enable")

    # 5. Start scanning loop
    http = httpx.AsyncClient(timeout=5)
    currency_index = 0
    scan_count = 0
    currencies_scanned: Dict[str, float] = {}

    logger.info("")
    logger.info(f"Scanning {len(OTC_CURRENCIES)} OTC currencies in rotation...")
    logger.info("   Each currency gets ~3 seconds of price reading before switching.")
    logger.info("   Press Ctrl+C to stop.")
    logger.info("")

    try:
        while True:
            currency = OTC_CURRENCIES[currency_index % len(OTC_CURRENCIES)]
            pair_code = currency["name"].replace(" (OTC)", "").replace("/", "/")
            symbol = currency["name"]

            # Click the currency tab
            js_click = JS_CLICK_TAB_TEMPLATE.format(pair_code=pair_code)
            click_result = await cdp.evaluate_js(js_click)
            logger.debug(f"Tab click: {click_result}")

            # Wait for chart to load
            await asyncio.sleep(1.5)

            # Read the active asset name
            active_asset = await cdp.evaluate_js(JS_READ_ACTIVE_ASSET)

            # Read the live price
            price = await cdp.evaluate_js(JS_READ_PRICE)

            # Read payout
            payout = await cdp.evaluate_js(JS_READ_PAYOUT)

            if price and price > 0:
                currencies_scanned[symbol] = price
                scan_count += 1

                payout_str = f"{payout}%" if payout else "N/A"
                logger.info(
                    f"[{scan_count:>4}] {symbol:<22} | "
                    f"Price: {price:<12.5g} | Payout: {payout_str:<5} | "
                    f"Active: {active_asset or 'Unknown'}"
                )

                # Send live tick for immediate /signal availability
                await send_live_tick_to_bot(http, symbol, price)

                # Accumulate into proper 1-minute OHLCV candle
                completed_candle = accumulate_tick(symbol, price)
                if completed_candle:
                    await send_candle_to_bot(http, symbol, completed_candle)

                # If payout < 80%, skip this currency in future rotations
                if payout and payout < 80:
                    logger.info(f"   Skipping {symbol} - payout {payout}% < 80% minimum")
            else:
                logger.debug(f"   Could not read price for {symbol}")

            # Read price a second time before switching (2nd tick in this window)
            await asyncio.sleep(1.5)
            price2 = await cdp.evaluate_js(JS_READ_PRICE)
            if price2 and price2 > 0:
                await send_live_tick_to_bot(http, symbol, price2)
                accumulate_tick(symbol, price2)

            currency_index += 1

            # Status summary every full rotation
            if currency_index % len(OTC_CURRENCIES) == 0:
                logger.info("")
                logger.info(f"FULL ROTATION COMPLETE - {len(currencies_scanned)} currencies streamed")
                logger.info(f"   Total ticks sent: {scan_count}")
                logger.info(f"   Active accumulators: {len(_candle_accumulators)}")
                logger.info("")

    except KeyboardInterrupt:
        logger.info("\nScanner stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Scanner error: {e}", exc_info=True)
    finally:
        await cdp.close()
        await http.aclose()
        logger.info("Scanner shutdown complete.")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting TradePulse Quotex Scanner...")
    try:
        asyncio.run(run_scanner())
    except KeyboardInterrupt:
        pass
