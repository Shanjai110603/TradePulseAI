"""
TradePulse AI — Free 24/7 Quotex Live Market Data Cloud Relay
Deploy this on a free service (Hugging Face Spaces, Render, or any free Python host)
It pulls real market candles and automatically pushes them to your AWS EC2 Bot.
"""

import asyncio
import json
import time
import os
import httpx
import websockets

# Your AWS EC2 Backend Ingestion URL
BACKEND_INGEST_URL = os.getenv("BACKEND_INGEST_URL", "http://13.48.58.176:8000/api/v1/markets/candles/ingest")

# Quotex WebSocket Server Endpoints
WS_URLS = [
    "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket",
    "wss://ws.qxbroker.com/socket.io/?EIO=3&transport=websocket",
]

WATCH_ASSETS = [
    # Forex OTC Pairs
    ("EUR/USD (OTC)", "EURUSD_otc"),
    ("GBP/USD (OTC)", "GBPUSD_otc"),
    ("USD/JPY (OTC)", "USDJPY_otc"),
    ("USD/CHF (OTC)", "USDCHF_otc"),
    ("AUD/USD (OTC)", "AUDUSD_otc"),
    ("USD/CAD (OTC)", "USDCAD_otc"),
    ("NZD/USD (OTC)", "NZDUSD_otc"),
    ("EUR/GBP (OTC)", "EURGBP_otc"),
    ("EUR/JPY (OTC)", "EURJPY_otc"),
    ("GBP/JPY (OTC)", "GBPJPY_otc"),
    ("AUD/CAD (OTC)", "AUDCAD_otc"),
    ("AUD/JPY (OTC)", "AUDJPY_otc"),
    ("CAD/JPY (OTC)", "CADJPY_otc"),
    ("CHF/JPY (OTC)", "CHFJPY_otc"),
    ("EUR/AUD (OTC)", "EURAUD_otc"),
    ("EUR/CAD (OTC)", "EURCAD_otc"),
    ("EUR/CHF (OTC)", "EURCHF_otc"),
    ("GBP/AUD (OTC)", "GBPAUD_otc"),
    ("GBP/CAD (OTC)", "GBPCAD_otc"),
    ("GBP/CHF (OTC)", "GBPCHF_otc"),
    ("NZD/JPY (OTC)", "NZDJPY_otc"),
    ("NZD/CAD (OTC)", "NZDCAD_otc"),
    ("USD/INR (OTC)", "USDINR_otc"),
    ("USD/BRL (OTC)", "USDBRL_otc"),
    ("USD/TRY (OTC)", "USDTRY_otc"),
    ("USD/MXN (OTC)", "USDMXN_otc"),

    # Crypto Pairs
    ("BTC/USDT (OTC)", "BTCUSD_otc"),
    ("ETH/USDT (OTC)", "ETHUSD_otc"),
    ("LTC/USDT (OTC)", "LTCUSD_otc"),
    ("XRP/USDT (OTC)", "XRPUSD_otc"),
    ("SOL/USDT (OTC)", "SOLUSD_otc"),
    ("DOGE/USDT (OTC)", "DOGEUSD_otc"),

    # Commodities OTC
    ("GOLD (OTC)", "XAUUSD_otc"),
    ("SILVER (OTC)", "XAGUSD_otc"),
    ("US CRUDE (OTC)", "UKBrent_otc"),

    # Live Standard Forex Market
    ("EUR/USD", "EURUSD"),
    ("GBP/USD", "GBPUSD"),
    ("USD/JPY", "USDJPY"),
    ("AUD/USD", "AUDUSD"),
    ("USD/CAD", "USDCAD"),
    ("USD/CHF", "USDCHF"),
    ("EUR/JPY", "EURJPY"),
    ("GBP/JPY", "GBPJPY"),
]

async def get_live_quotex_session() -> str:
    """Extracts live Quotex session token by signing in with email & password via Playwright or demo-trade"""
    env_token = os.getenv("QUOTEX_SESSION_TOKEN")
    if env_token:
        return env_token

    email = os.getenv("QUOTEX_EMAIL", "")
    password = os.getenv("QUOTEX_PASSWORD", "")

    try:
        import importlib
        playwright_module = importlib.import_module("playwright.async_api")
        async_playwright = getattr(playwright_module, "async_playwright")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            if email and password:
                print(f"[BROWSER] Logging in to Quotex as {email[:4]}*** via Headless Chromium...", flush=True)
                signin_urls = [
                    "https://qxbroker.com/en/sign-in",
                    "https://market-qx.pro/en/sign-in",
                    "https://quotex.com/en/sign-in",
                ]
                for signin_url in signin_urls:
                    try:
                        await page.goto(signin_url, wait_until="domcontentloaded", timeout=25000)
                        await asyncio.sleep(2.0)
                        email_input = page.locator('input[type="email"], input[name="email"]')
                        if await email_input.count() > 0:
                            await email_input.first.fill(email)
                            await page.fill('input[type="password"], input[name="password"]', password)
                            submit_btn = page.locator('button[type="submit"]')
                            if await submit_btn.count() > 0:
                                await submit_btn.first.click()
                            else:
                                await page.keyboard.press("Enter")
                            await asyncio.sleep(6.0)
                            print("[BROWSER] Credentials submitted successfully!", flush=True)
                            break
                    except Exception as signin_err:
                        print(f"[BROWSER NOTICE] Attempt with {signin_url}: {signin_err}", flush=True)
            else:
                print("[BROWSER] Navigating to https://qxbroker.com/en/demo-trade to acquire guest session...", flush=True)
                await page.goto("https://qxbroker.com/en/demo-trade", wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(3.0)

            token = await page.evaluate("() => localStorage.getItem('token') || localStorage.getItem('session') || ''")
            cookies = await context.cookies()
            cookie_session = next((c['value'] for c in cookies if c['name'] in ['session', 'token', 'PHPSESSID', 'ssid']), None)
            await browser.close()
            final_token = token or cookie_session or ""
            if final_token:
                print(f"[BROWSER] Successfully captured authentic Quotex session token: {final_token[:15]}...", flush=True)
            return final_token
    except Exception as e:
        print(f"[BROWSER NOTICE] Headless browser session note: {e}", flush=True)
        return ""

async def push_candles_to_ec2(symbol: str, timeframe: str, candles: list):
    """Pushes candle batch to AWS EC2 backend"""
    try:
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(BACKEND_INGEST_URL, json=payload)
            if res.status_code == 200:
                print(f"[RELAY ➔ EC2] Ingested {len(candles)} real candles for {symbol}", flush=True)
            else:
                print(f"[RELAY] Failed push ({res.status_code}): {res.text}", flush=True)
    except Exception as e:
        print(f"[RELAY ERROR] Failed to push to EC2: {e}", flush=True)

async def run_relay():
    print(f"[*] Starting TradePulse Free Cloud Relay -> Target: {BACKEND_INGEST_URL}", flush=True)
    
    # Obtain authentic session token on start
    session_token = await get_live_quotex_session()

    while True:
        for ws_url in WS_URLS:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Origin": "https://qxbroker.com"
                }
                async with websockets.connect(ws_url, additional_headers=headers, open_timeout=12, close_timeout=5) as ws:
                    init_msg = await asyncio.wait_for(ws.recv(), timeout=6)
                    print(f"[WS] Connected to {ws_url} (Handshake: {str(init_msg)[:60]})", flush=True)

                    # Send Socket.IO namespace connect
                    await ws.send("40")
                    
                    # Send authorization if token available
                    if session_token:
                        auth_msg = json.dumps(["authorization", {"session": session_token, "isDemo": 1, "tournamentId": 0}])
                        await ws.send(f"42{auth_msg}")
                        print(f"[WS AUTH] Sent Quotex session authorization packet", flush=True)
                    else:
                        print(f"[WS] Streaming live market data...", flush=True)

                    await asyncio.sleep(0.5)

                    # Continuous streaming loop
                    while True:
                        for symbol, ws_asset in WATCH_ASSETS:
                            end_time = int(time.time())
                            req = json.dumps(["history/load", {"asset": ws_asset, "period": 60, "time": end_time, "count": 50}])
                            await ws.send(f"42{req}")
                            await asyncio.sleep(0.15)

                        deadline = asyncio.get_event_loop().time() + 8
                        while asyncio.get_event_loop().time() < deadline:
                            try:
                                raw = await asyncio.wait_for(ws.recv(), timeout=2)
                                if isinstance(raw, bytes):
                                    raw = raw.decode("utf-8", errors="ignore")
                                if raw == "2":
                                    await ws.send("3")
                                    continue
                                if raw == "41":
                                    print("[WS NOTICE] Session refresh required. Re-authenticating...", flush=True)
                                    session_token = await get_live_quotex_session()
                                    break
                                if raw.startswith("42"):
                                    data = json.loads(raw[2:])
                                    if isinstance(data, list) and len(data) >= 2:
                                        event = str(data[0])
                                        payload = data[1]
                                        if "history" in event and isinstance(payload, dict):
                                            candles_raw = payload.get("candles", [])
                                            asset_name = payload.get("asset", "")
                                            matched_symbol = next((s for s, a in WATCH_ASSETS if a == asset_name), None)
                                            if matched_symbol and candles_raw:
                                                converted = [
                                                    {
                                                        "time": int(c[0]),
                                                        "open": float(c[1]),
                                                        "close": float(c[2]),
                                                        "high": float(c[3]),
                                                        "low": float(c[4]),
                                                        "volume": 1200
                                                    }
                                                    for c in candles_raw if isinstance(c, (list, tuple)) and len(c) >= 5
                                                ]
                                                if converted:
                                                    await push_candles_to_ec2(matched_symbol, "1M", converted)
                            except asyncio.TimeoutError:
                                break

            except Exception as err:
                print(f"[WS DISCONNECT] {err}. Reconnecting in 5 seconds...", flush=True)
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_relay())
