"""
Quotex Live Browser Relay
==========================
This is the "real data" fix.

Why this exists:
    The old approach hand-rolled Quotex's private socket.io auth handshake
    and replayed it blind. Quotex owns that protocol and can change it
    without notice, so that approach was fragile and, on failure, the old
    code silently fell back to fabricated numbers.

What this does instead:
    It drives an ACTUAL, logged-in Chromium browser (via Playwright) that
    sits on the real Quotex trading page. Quotex's own frontend JS does all
    the authentication. This script just listens in on the websocket frames
    that browser session naturally exchanges with Quotex's server — the
    exact same data a human trader watching the chart would see — and
    forwards genuine candles to the backend's /markets/candles/ingest
    endpoint. It also cycles through your configured asset list so the
    "currency auto-switch" feature has real data for every pair, not just
    whichever chart happens to be open.

Run this as its OWN process, separate from the FastAPI backend. A headless
browser is memory-heavy; isolating it means if it crashes or gets stuck, it
doesn't take your API/Telegram bot down with it (and vice versa).

    python -m app.relay.quotex_browser_relay

First run will need QUOTEX_EMAIL / QUOTEX_PASSWORD in your .env (or an
existing storage_state.json — see save_login.py) to log in once; after that,
the session is cached to disk and reused.

IMPORTANT — selectors may need adjusting:
    Quotex's frontend markup can change. The CSS selectors below are
    best-effort based on common patterns and this repo's own login flow.
    If login or asset-switching stops working, run with `--headed` locally,
    watch what happens, and update SELECTORS below. Debug screenshots are
    auto-saved to uploads/relay_debug/ on failure to make this easier.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # allow `app.*` imports when run as a script

from app.core.config import settings
from app.engine.market_data.quotex_provider import QUOTEX_ASSETS
from app.engine.market_data.quotex_frame_parser import (
    parse_socketio_frame,
    extract_candles_from_payload,
    extract_tick_from_payload,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("quotex_relay")

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
STORAGE_STATE_PATH = BASE_DIR / "uploads" / "quotex_storage_state.json"
DEBUG_DIR = BASE_DIR / "uploads" / "relay_debug"

QUOTEX_TRADE_URLS = [
    "https://qxbroker.com/en/trade",
    "https://market-qx.pro/en/trade",
]
QUOTEX_SIGNIN_URLS = [
    "https://qxbroker.com/en/sign-in",
    "https://market-qx.pro/en/sign-in",
]

# --- VERIFIED DOM SELECTORS for Quotex Trading Terminal --------------------
SELECTORS = {
    "email_input": 'input[type="email"], input[name="email"]',
    "password_input": 'input[type="password"], input[name="password"]',
    "submit_button": 'button[type="submit"], form button, .auth-form button',
    # Blue [+] button in top bar or active asset badge trigger
    "asset_switcher_trigger": (
        'button:has-text("+"), .tabs__add, [class*="tabs__add"], [class*="tab-add"], '
        '[class*="asset-select"], [class*="pair-select"], '
        '.tab-item.active, [class*="tab"].active, [class*="current-asset"]'
    ),
    "asset_search_input": 'input[placeholder*="Search" i], input[type="search"], .modal input',
}
# ---------------------------------------------------------------------------

DEFAULT_TIMEFRAME = "1M"
SECONDS_PER_ASSET = 25          # how long to sit on each asset gathering frames
INGEST_FLUSH_INTERVAL = 5.0     # push whatever we've buffered at least this often
RELAY_TARGET_URL = os.environ.get(
    "RELAY_TARGET_URL",
    f"http://127.0.0.1:{os.environ.get('PORT', 8000)}{settings.API_V1_STR}/markets/candles/ingest",
)


class AssetBuffer:
    """Accumulates candles/ticks captured for one asset between flushes."""
    def __init__(self):
        self.candles: Dict[int, dict] = {}   # keyed by timestamp to dedupe
        self.last_tick_price: Optional[float] = None
        self.last_tick_time: Optional[int] = None

    def add_candles(self, candles: List[dict]):
        for c in candles:
            self.candles[c["time"]] = c

    def add_tick(self, price: float, ts: Optional[int]):
        self.last_tick_price = price
        self.last_tick_time = ts or int(time.time())

    def pop_payload(self) -> List[dict]:
        """Returns candles to send, including a synthetic 1-tick candle if that's all we have."""
        out = list(self.candles.values())
        self.candles.clear()
        if not out and self.last_tick_price is not None:
            out = [{
                "time": self.last_tick_time,
                "open": self.last_tick_price,
                "high": self.last_tick_price,
                "low": self.last_tick_price,
                "close": self.last_tick_price,
            }]
        return out


class QuotexBrowserRelay:
    def __init__(self, assets: List[str], headless: bool = True):
        self.assets = assets
        self.headless = headless
        self.buffers: Dict[str, AssetBuffer] = {a: AssetBuffer() for a in assets}
        self.http = httpx.AsyncClient(timeout=10.0)
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    async def run_forever(self):
        while True:
            try:
                await self._run_session()
            except Exception as e:
                logger.error(f"[RELAY] Session crashed, restarting in 15s: {e}", exc_info=True)
            await asyncio.sleep(15)

    async def _run_session(self):
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("[RELAY] Playwright is not installed. Run: pip install playwright && playwright install chromium")
            raise

    async def _run_session(self):
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("[RELAY] Playwright is not installed. Run: pip install playwright && playwright install chromium")
            raise

        async with async_playwright() as p:
            context = None
            is_cdp = False

            # Tier 1: Check if genuine Chrome is ALREADY running with Quotex open on port 9222!
            try:
                r = await self.http.get("http://127.0.0.1:9222/json/version", timeout=1.5)
                if r.status_code == 200:
                    logger.info("[RELAY] Detected open Chrome terminal on port 9222! Connecting directly via CDP...")
                    browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                    context = browser.contexts[0] if browser.contexts else await browser.new_context()
                    is_cdp = True
                    logger.info("[RELAY] Connected to your active Chrome browser via CDP. Zero Cloudflare required!")
            except Exception:
                pass

            # Tier 2: Launch genuine retail Google Chrome with persistent profile
            if not context:
                profile_dir = BASE_DIR / "uploads" / "chrome_profile"
                profile_dir.mkdir(parents=True, exist_ok=True)
                args = [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ]

                try:
                    logger.info("[RELAY] Launching genuine retail Google Chrome (channel='chrome')...")
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir=str(profile_dir),
                        channel="chrome",  # Genuine Chrome avoids 'Chrome for Testing' flags
                        headless=self.headless,
                        viewport={"width": 1400, "height": 900},
                        args=args,
                    )
                except Exception as e:
                    logger.info(f"[RELAY] Retail Chrome channel unavailable ({e}), launching standard Chromium...")
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir=str(profile_dir),
                        headless=self.headless,
                        viewport={"width": 1400, "height": 900},
                        args=args,
                    )

            # Mask webdriver property on all pages
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Attach WebSocket listener to any existing or new tabs
            for pg in context.pages:
                pg.on("websocket", lambda ws: self._attach_ws_listener(ws))
            context.on("page", lambda pg: pg.on("websocket", lambda ws: self._attach_ws_listener(ws)))

            # Find active Quotex page or create one
            page = None
            for pg in context.pages:
                if any(domain in pg.url for domain in ("qxbroker.com", "market-qx.pro", "quotex.com")):
                    page = pg
                    break

            if not page:
                page = context.pages[0] if context.pages else await context.new_page()

            page.on("websocket", lambda ws: self._attach_ws_listener(ws))

            logger.info("[RELAY] Verifying Quotex trading session...")
            logged_in = await self._ensure_logged_in(page, context)
            if not logged_in:
                await self._debug_screenshot(page, "login_failed")
                raise RuntimeError("Could not establish a logged-in Quotex session")

            flush_task = asyncio.create_task(self._flush_loop())
            try:
                await self._cycle_assets(page)
            finally:
                flush_task.cancel()
                if not is_cdp:
                    await context.close()

    async def _is_trade_ui_active(self, page) -> bool:
        """Verifies if the real Quotex trading canvas/terminal is loaded (not Cloudflare)."""
        try:
            title = (await page.title()).lower()
            if "just a moment" in title or "security verification" in title:
                return False
            ui = page.locator('.deal-form, [class*="deal-form"], .tab-item, [class*="tab"], .chart__current-price, button:has-text("+")')
            return (await ui.count()) > 0
        except Exception:
            return False

    async def _wait_for_cloudflare(self, page, max_seconds: int = 60) -> bool:
        """If Cloudflare Turnstile appears, waits for user to click or auto-clearance."""
        for i in range(max_seconds):
            if await self._is_trade_ui_active(page):
                return True
            title = (await page.title()).lower()
            if "just a moment" not in title and "security verification" not in title:
                try:
                    text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                    if "Performing security verification" not in text and "Verify you are human" not in text:
                        return True
                except Exception:
                    pass
            if i % 5 == 0:
                logger.info(f"[RELAY] Cloudflare Turnstile active ({i}/{max_seconds}s) — please click the checkbox if visible.")
            # Auto-click Turnstile checkbox inside iframes if accessible
            try:
                for frame in page.frames:
                    box = frame.locator('input[type="checkbox"], .ctp-checkbox-label, #challenge-stage')
                    if await box.count() > 0:
                        await box.first.click(timeout=1000)
                        logger.info("[RELAY] Clicked Cloudflare Turnstile checkbox.")
                        break
            except Exception:
                pass
            await asyncio.sleep(1)
        return await self._is_trade_ui_active(page)

    async def _ensure_logged_in(self, page, context) -> bool:
        for url in QUOTEX_TRADE_URLS:
            try:
                logger.info(f"[RELAY] Checking trade page directly: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                # Check if Cloudflare is present
                title = (await page.title()).lower()
                if "just a moment" in title or "security verification" in title:
                    logger.info("[RELAY] Cloudflare Turnstile detected on trade page.")
                    await self._wait_for_cloudflare(page, max_seconds=60)

                if await self._is_trade_ui_active(page):
                    logger.info(f"[RELAY] Trade UI is active and authenticated at {page.url}")
                    return True
            except Exception as e:
                logger.info(f"[RELAY] Trade page check at {url}: {e}")

        email = settings.QUOTEX_EMAIL
        password = settings.QUOTEX_PASSWORD
        if not email or not password:
            logger.error("[RELAY] No saved session and no QUOTEX_EMAIL/QUOTEX_PASSWORD configured — cannot log in.")
            return False

        for url in QUOTEX_SIGNIN_URLS:
            try:
                logger.info(f"[RELAY] Logging in via {url} ...")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                # Check if Cloudflare is on the sign-in page
                title = (await page.title()).lower()
                if "just a moment" in title or "security verification" in title:
                    logger.info("[RELAY] Cloudflare Turnstile detected on sign-in page.")
                    await self._wait_for_cloudflare(page, max_seconds=60)

                email_input = page.locator(SELECTORS["email_input"])
                if await email_input.count() == 0:
                    continue
                logger.info(f"[RELAY] Entering credentials for {email}...")
                await email_input.first.fill(email)
                await page.fill(SELECTORS["password_input"], password)
                submit = page.locator(SELECTORS["submit_button"])
                if await submit.count() > 0:
                    await submit.first.click()
                else:
                    await page.keyboard.press("Enter")

                for _ in range(15):
                    await asyncio.sleep(1)
                    if await self._is_trade_ui_active(page):
                        logger.info("[RELAY] Login successful. Quotex terminal is ready!")
                        return True

                if await self._is_trade_ui_active(page):
                    return True
            except Exception as e:
                logger.debug(f"[RELAY] Login attempt at {url} failed: {e}")
                continue

        return await self._is_trade_ui_active(page)

    async def _save_storage_state(self, context):
        try:
            STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(STORAGE_STATE_PATH))
            logger.info(f"[RELAY] Saved session to {STORAGE_STATE_PATH} for reuse on next run.")
        except Exception as e:
            logger.warning(f"[RELAY] Could not save storage state: {e}")

    def _attach_ws_listener(self, ws):
        logger.debug(f"[RELAY] Observing websocket: {ws.url}")
        ws.on("framereceived", lambda payload: self._on_frame(payload))

    def _on_frame(self, payload):
        try:
            raw = payload if isinstance(payload, str) else payload.decode("utf-8", errors="ignore")
        except Exception:
            return
        decoded = parse_socketio_frame(raw)
        if not decoded:
            return
        event, data = decoded
        if event in ("__ping__", "__reject__"):
            return

        candles = extract_candles_from_payload(event, data)
        if candles:
            asset = self._match_asset_from_event(event, data)
            if asset:
                self.buffers[asset].add_candles(candles)
            return

        tick = extract_tick_from_payload(event, data)
        if tick and tick.get("asset"):
            asset = self._match_asset_from_event(event, {"asset": tick["asset"]})
            if asset:
                self.buffers[asset].add_tick(tick["price"], tick.get("time"))

    def _match_asset_from_event(self, event: str, data) -> Optional[str]:
        """Maps a raw ws_asset code (e.g. 'EURUSD_otc') back to our display symbol."""
        ws_asset = None
        if isinstance(data, dict):
            ws_asset = data.get("asset")
        if not ws_asset:
            return None
        for a in QUOTEX_ASSETS:
            if a["ws_asset"] == ws_asset and a["symbol"] in self.buffers:
                return a["symbol"]
        return None

    async def _cycle_assets(self, page):
        """Rotates the visible chart through every configured asset so each one
        gets genuine traffic to sniff. This IS the auto-currency-switch behavior —
        the backend scheduler already scans all assets each tick; this just makes
        sure real data exists for it to scan."""
        while True:
            for symbol in self.assets:
                switched = await self._switch_asset(page, symbol)
                if not switched:
                    logger.debug(f"[RELAY] Could not switch UI to {symbol}; still listening on whatever is active.")
                await asyncio.sleep(SECONDS_PER_ASSET)

    async def _switch_asset(self, page, symbol: str) -> bool:
        """Robust multi-tier UI automation to switch to `symbol` on the Quotex trade page."""
        clean_slash = symbol.replace(" (OTC)", "").strip()
        clean_no_slash = clean_slash.replace("/", "")

        try:
            # Tier 1: Direct Click if the tab is already visible in the top bar
            tab_selectors = [
                f'.tab-item:has-text("{clean_slash}")',
                f'[class*="tab"]:has-text("{clean_slash}")',
                f'button:has-text("{clean_slash}")',
                f'.tab-item:has-text("{clean_no_slash}")',
            ]
            for sel in tab_selectors:
                tabs = page.locator(sel)
                count = await tabs.count()
                for i in range(count):
                    t = tabs.nth(i)
                    box = await t.bounding_box()
                    if box and box["y"] < 150:
                        await t.click()
                        logger.info(f"[RELAY] Switched to {symbol} via open tab click")
                        return True

            # Tier 2: Open modal via Blue [+] button or active tab trigger
            trigger = page.locator(SELECTORS["asset_switcher_trigger"])
            if await trigger.count() > 0:
                clicked = False
                for i in range(await trigger.count()):
                    el = trigger.nth(i)
                    box = await el.bounding_box()
                    if box and (box["y"] < 150 or box["x"] > 1000):
                        await el.click()
                        clicked = True
                        break
                if not clicked:
                    await trigger.first.click()
                await asyncio.sleep(0.5)

            # Tier 3: Search for target currency in modal
            search = page.locator(SELECTORS["asset_search_input"])
            if await search.count() > 0:
                await search.first.fill(clean_slash)
                await asyncio.sleep(0.5)

            # Tier 4: Select row in modal list
            row_selectors = [
                f'[class*="asset-item"]:has-text("{clean_slash}")',
                f'[class*="table__item"]:has-text("{clean_slash}")',
                f'.modal :text("{clean_slash}")',
                f':text("{clean_slash}")',
            ]
            for r_sel in row_selectors:
                rows = page.locator(r_sel)
                if await rows.count() > 0:
                    await rows.first.click()
                    logger.info(f"[RELAY] Switched to {symbol} via modal row click")
                    return True

        except Exception as e:
            logger.debug(f"[RELAY] _switch_asset({symbol}) failed: {e}")
            await self._debug_screenshot(page, f"switch_failed_{clean_no_slash}")

        return False

    async def _debug_screenshot(self, page, label: str):
        try:
            path = DEBUG_DIR / f"{int(time.time())}_{label}.png"
            await page.screenshot(path=str(path))
            logger.info(f"[RELAY] Saved debug screenshot: {path}")
        except Exception:
            pass

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(INGEST_FLUSH_INTERVAL)
            for symbol, buf in self.buffers.items():
                payload = buf.pop_payload()
                if not payload:
                    continue
                try:
                    resp = await self.http.post(
                        RELAY_TARGET_URL,
                        params={"api_key": settings.RELAY_API_KEY},
                        json={"symbol": symbol, "timeframe": DEFAULT_TIMEFRAME, "candles": payload},
                    )
                    if resp.status_code == 200:
                        logger.info(f"[RELAY] Ingested {len(payload)} candle(s) for {symbol}")
                    else:
                        logger.warning(f"[RELAY] Ingest rejected for {symbol}: {resp.status_code} {resp.text[:200]}")
                except Exception as e:
                    logger.warning(f"[RELAY] Failed to push {symbol} to backend: {e}")


def main():
    print("[RELAY] Initializing Quotex Browser Relay...", flush=True)
    logger.info("[RELAY] Starting Quotex Browser Relay process...")
    parser = argparse.ArgumentParser(description="Quotex live browser relay")
    parser.add_argument("--headed", action="store_true", help="Show the browser window (useful for fixing selectors)")
    parser.add_argument("--assets", type=str, default="", help="Comma-separated subset of symbols to watch (default: all OTC pairs)")
    args = parser.parse_args()

    if args.assets:
        assets = [s.strip() for s in args.assets.split(",") if s.strip()]
    else:
        assets = [a["symbol"] for a in QUOTEX_ASSETS if a["is_otc"]]

    print(f"[RELAY] Mode: {'Headed (Visible)' if args.headed else 'Headless'}, Tracking {len(assets)} assets.", flush=True)
    logger.info(f"[RELAY] Mode: {'Headed (Visible)' if args.headed else 'Headless'}, Tracking {len(assets)} assets.")
    relay = QuotexBrowserRelay(assets=assets, headless=not args.headed)
    asyncio.run(relay.run_forever())


if __name__ == "__main__":
    main()
