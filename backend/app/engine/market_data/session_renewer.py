"""
Quotex Automated Headless Session Renewer
==========================================
Automatically logs in using QUOTEX_EMAIL and QUOTEX_PASSWORD via Playwright/HTTP
and extracts the latest active session cookies (SSID).

Runs in the background so the bot maintains a perpetual, auto-renewing live connection
without ever requiring manual browser cookie extraction.
"""
import os
import json
import time
import asyncio
import logging
from typing import Optional, Dict, List
import httpx

logger = logging.getLogger(__name__)

SESSION_CACHE_FILE = "uploads/quotex_session.json"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days

QUOTEX_SIGNIN_URLS = [
    "https://qxbroker.com/en/sign-in",
    "https://market-qx.pro/en/sign-in",
    "https://quotex.com/en/sign-in",
    "https://quotex.io/en/sign-in",
]


class QuotexSessionRenewer:
    """
    Manages automated login, file caching, and session cookie renewal for Quotex.
    Matches A11ksa/API-Quotex session persistence pattern.
    """

    @classmethod
    async def get_session_cookies(cls, email: str, password: str, force_refresh: bool = False) -> Optional[str]:
        """
        Acquires an active SSID token for Quotex.
        Checks local session cache first; refreshes via Playwright/HTTP if missing or expired.
        """
        if not email or not password:
            logger.warning("[SESSION_RENEWER] Email or password not configured.")
            return None

        # 1. Check cached session file if not forcing refresh
        if not force_refresh:
            cached_token = cls._load_cached_session(email)
            if cached_token:
                logger.info("[SESSION_RENEWER] Using active cached Quotex session.")
                return cached_token

        # 2. Try Playwright Headless Browser (Full JS Execution)
        try:
            playwright_token = await cls._try_playwright_login(email, password)
            if playwright_token:
                logger.info("[SESSION_RENEWER] Successfully acquired fresh Quotex session via Playwright.")
                cls._save_cached_session(email, playwright_token)
                return playwright_token
        except Exception as e:
            logger.debug(f"[SESSION_RENEWER] Playwright login attempt notice: {e}")

        # 3. Try Direct HTTP Login with CSRF Extraction
        try:
            http_token = await cls._try_http_login(email, password)
            if http_token:
                logger.info("[SESSION_RENEWER] Successfully acquired Quotex session via Direct HTTP.")
                cls._save_cached_session(email, http_token)
                return http_token
        except Exception as e:
            logger.debug(f"[SESSION_RENEWER] HTTP direct login attempt notice: {e}")

        return None

    @classmethod
    def _load_cached_session(cls, email: str) -> Optional[str]:
        """Loads and validates cached session from disk."""
        if not os.path.exists(SESSION_CACHE_FILE):
            return None
        try:
            with open(SESSION_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_email = data.get("email")
            saved_time = data.get("timestamp", 0)
            token = data.get("token")
            # Validate email and TTL
            if saved_email == email and token and (time.time() - saved_time < SESSION_TTL_SECONDS):
                return token
        except Exception as e:
            logger.debug(f"[SESSION_RENEWER] Error reading session cache: {e}")
        return None

    @classmethod
    def _save_cached_session(cls, email: str, token: str):
        """Persists acquired session to disk."""
        try:
            os.makedirs(os.path.dirname(SESSION_CACHE_FILE), exist_ok=True)
            with open(SESSION_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "email": email,
                    "token": token,
                    "timestamp": time.time()
                }, f)
        except Exception as e:
            logger.debug(f"[SESSION_RENEWER] Error saving session cache: {e}")

    @classmethod
    async def _try_playwright_login(cls, email: str, password: str) -> Optional[str]:
        """Runs a headless browser login to pass Cloudflare/JS challenges and extract the session."""
        try:
            import importlib
            playwright_module = importlib.import_module("playwright.async_api")
            async_playwright = getattr(playwright_module, "async_playwright")
        except (ImportError, AttributeError):
            logger.debug("[SESSION_RENEWER] Playwright not installed in environment; skipping browser step.")
            return None

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
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            for url in QUOTEX_SIGNIN_URLS:
                try:
                    logger.info(f"[SESSION_RENEWER] Navigating to {url} via Headless Chromium...")
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)

                    # Look for email input
                    email_input = page.locator('input[type="email"], input[name="email"]')
                    if await email_input.count() > 0:
                        await email_input.first.fill(email)
                        await page.fill('input[type="password"], input[name="password"]', password)

                        # Click submit button
                        submit_btn = page.locator('button[type="submit"]')
                        if await submit_btn.count() > 0:
                            await submit_btn.first.click()
                        else:
                            await page.keyboard.press("Enter")

                        # Wait up to 10s for navigation / cookies to set
                        await asyncio.sleep(5)

                        # Extract cookies from browser context
                        cookies = await context.cookies()
                        cookie_dict = {c["name"]: c["value"] for c in cookies}

                        ssid = cookie_dict.get("ssid") or cookie_dict.get("token") or cookie_dict.get("laravel_session")
                        if ssid:
                            cookie_parts = []
                            for k in ["ssid", "laravel_session", "token"]:
                                if k in cookie_dict:
                                    cookie_parts.append(f"{k}={cookie_dict[k]}")
                            await browser.close()
                            return "; ".join(cookie_parts)

                except Exception as page_err:
                    logger.debug(f"[SESSION_RENEWER] Error with URL {url}: {page_err}")
                    continue

            await browser.close()
            return None

    @classmethod
    async def _try_http_login(cls, email: str, password: str) -> Optional[str]:
        """Direct HTTP POST login to Quotex authentication endpoint."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=8.0) as client:
            for url in QUOTEX_SIGNIN_URLS:
                try:
                    await client.get(url)
                    payload = {"email": email, "password": password, "remember": "1"}
                    await client.post(url, data=payload, headers={"Referer": url})

                    cookie_parts = []
                    for k, v in client.cookies.items():
                        if k in ["ssid", "laravel_session", "token"]:
                            cookie_parts.append(f"{k}={v}")

                    if cookie_parts:
                        return "; ".join(cookie_parts)
                except Exception:
                    continue

        return None
