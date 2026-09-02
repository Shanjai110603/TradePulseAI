"""
TradePulse Quotex Scanner — Self-Contained Windows Desktop Application
======================================================================
A FULL GUI Windows app that:
 - Launches Chrome with CDP (undetectable)
 - Scans 20+ OTC currencies automatically
 - Evaluates MTF_ENGULFING_1M strategy LOCALLY (no backend needed)
 - Takes REAL Quotex chart screenshots via CDP
 - Sends signal + screenshot directly to Telegram
 - Beautiful dark-themed dashboard with live prices

NO PORT 8000 NEEDED. Completely standalone.
"""

import asyncio
import base64
import json
import logging
import math
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Load environment configuration (.env)
# ---------------------------------------------------------------------------

def _load_env():
    # Look for .env in current dir, parent dir (project root), or C:\TradePulse
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
        Path(r"C:\TradePulse\.env"),
        Path(r"C:\TradePulse\backend\.env"),
    ]
    for p in candidates:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
                break
            except Exception:
                pass

_load_env()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_NAME = "TradePulse Quotex Scanner"
APP_VERSION = "2.0.0"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CDP_PORT = 9222
CHROME_USER_DATA = str(Path.home() / "QuotexScannerProfile")
QUOTEX_TRADE_URL = "https://qxbroker.com/en/trade"

# Telegram config - reads from environment or uses defaults
TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8928508919:AAH49-CwlHxX7EZnDrMixVUVNsMUCzp56uM"
)
TELEGRAM_CHAT_IDS = [cid.strip() for cid in os.environ.get("TELEGRAM_CHAT_IDS", "8899287239").split(",") if cid.strip()]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

SCREENSHOTS_DIR = str(Path.home() / "TradePulseScreenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# All OTC currencies
OTC_CURRENCIES = [
    {"name": "EUR/USD (OTC)", "code": "EUR/USD", "precision": 5, "payout": 95},
    {"name": "GBP/USD (OTC)", "code": "GBP/USD", "precision": 5, "payout": 95},
    {"name": "USD/JPY (OTC)", "code": "USD/JPY", "precision": 3, "payout": 82},
    {"name": "AUD/USD (OTC)", "code": "AUD/USD", "precision": 5, "payout": 85},
    {"name": "USD/CHF (OTC)", "code": "USD/CHF", "precision": 5, "payout": 85},
    {"name": "USD/CAD (OTC)", "code": "USD/CAD", "precision": 5, "payout": 85},
    {"name": "NZD/USD (OTC)", "code": "NZD/USD", "precision": 5, "payout": 93},
    {"name": "EUR/GBP (OTC)", "code": "EUR/GBP", "precision": 5, "payout": 85},
    {"name": "EUR/JPY (OTC)", "code": "EUR/JPY", "precision": 3, "payout": 85},
    {"name": "GBP/JPY (OTC)", "code": "GBP/JPY", "precision": 3, "payout": 85},
    {"name": "AUD/CAD (OTC)", "code": "AUD/CAD", "precision": 5, "payout": 85},
    {"name": "AUD/JPY (OTC)", "code": "AUD/JPY", "precision": 3, "payout": 84},
    {"name": "USD/INR (OTC)", "code": "USD/INR", "precision": 3, "payout": 88},
    {"name": "USD/BRL (OTC)", "code": "USD/BRL", "precision": 4, "payout": 95},
    {"name": "USD/PKR (OTC)", "code": "USD/PKR", "precision": 3, "payout": 92},
    {"name": "USD/ZAR (OTC)", "code": "USD/ZAR", "precision": 4, "payout": 93},
    {"name": "NZD/CAD (OTC)", "code": "NZD/CAD", "precision": 5, "payout": 93},
    {"name": "USD/MXN (OTC)", "code": "USD/MXN", "precision": 4, "payout": 85},
    {"name": "USD/TRY (OTC)", "code": "USD/TRY", "precision": 4, "payout": 85},
    {"name": "USD/EGP (OTC)", "code": "USD/EGP", "precision": 3, "payout": 89},
]

# Color Palette
COLORS = {
    "bg_dark": "#0a0e17",
    "bg_card": "#111827",
    "bg_header": "#0d1321",
    "accent_green": "#00e676",
    "accent_red": "#ff1744",
    "accent_blue": "#2979ff",
    "accent_gold": "#ffd600",
    "accent_purple": "#bb86fc",
    "text_primary": "#e8eaed",
    "text_secondary": "#9aa0a6",
    "text_dim": "#5f6368",
    "border": "#1e2a3a",
    "btn_start": "#00c853",
    "btn_stop": "#ff1744",
    "btn_pause": "#ff9100",
}


# ---------------------------------------------------------------------------
# Candle Data Model
# ---------------------------------------------------------------------------

@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 100.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def total_range(self) -> float:
        return max(self.high - self.low, 1e-8)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


# ---------------------------------------------------------------------------
# MTF_ENGULFING_1M Strategy Evaluator (Self-Contained)
# ---------------------------------------------------------------------------

class StrategyEvaluator:
    """
    Evaluates the MTF_ENGULFING_1M strategy locally.
    No backend server needed.
    """

    @staticmethod
    def compute_ema(values: List[float], period: int) -> float:
        """Compute EMA for a list of values."""
        if not values:
            return 0.0
        period = min(period, len(values))
        if period <= 0:
            return values[-1]
        k = 2.0 / (period + 1)
        ema = values[0]
        for v in values[1:]:
            ema = v * k + ema * (1 - k)
        return ema

    @staticmethod
    def aggregate_to_5m(candles_1m: List[Candle]) -> List[Candle]:
        """Aggregate 1M candles into 5M candles."""
        if len(candles_1m) < 5:
            return candles_1m[-1:] if candles_1m else []

        result = []
        # Group by 5-minute boundaries
        for i in range(0, len(candles_1m) - 4, 5):
            group = candles_1m[i:i + 5]
            if len(group) >= 2:
                result.append(Candle(
                    timestamp=group[0].timestamp,
                    open=group[0].open,
                    high=max(c.high for c in group),
                    low=min(c.low for c in group),
                    close=group[-1].close,
                    volume=sum(c.volume for c in group),
                ))

        # Handle remaining candles
        remaining = len(candles_1m) % 5
        if remaining > 0:
            group = candles_1m[-remaining:]
            result.append(Candle(
                timestamp=group[0].timestamp,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            ))

        return result

    @classmethod
    def evaluate_mtf_engulfing(
        cls,
        candles: List[Candle],
        payout_pct: float = 85,
    ) -> Tuple[bool, str, Dict]:
        """
        Evaluate MTF_ENGULFING_1M strategy.
        Returns (matched, reason, details).
        """
        # Minimum payout filter
        if payout_pct < 80:
            return False, f"Payout {payout_pct}% < 80% minimum", {}

        if len(candles) < 6:
            return False, f"Need 6+ candles, have {len(candles)}", {}

        c = candles[-1]
        prev = candles[-2]

        rng_c = c.total_range
        body_c = c.body_size
        upper_wick_c = c.upper_wick
        lower_wick_c = c.lower_wick

        rng_prev = prev.total_range
        body_prev = prev.body_size

        # Avoid Rule 4: Doji Filter
        if (body_prev / rng_prev) < 0.10:
            return False, f"Doji filter: prev body {body_prev/rng_prev*100:.1f}% < 10%", {}

        # Body > 65% of range
        body_ratio = body_c / rng_c
        if body_ratio <= 0.65:
            return False, f"Body ratio {body_ratio*100:.1f}% <= 65%", {}

        # Anomaly spike filter
        if len(candles) >= 5:
            avg_prev_3 = sum(k.total_range for k in candles[-4:-1]) / 3.0
            if rng_c > (3.0 * avg_prev_3):
                return False, "Anomaly spike filter triggered", {}

        # 5M aggregation
        candles_5m = cls.aggregate_to_5m(candles)
        c_5m = candles_5m[-1] if candles_5m else c

        ema_20_5m = cls.compute_ema(
            [b.close for b in candles_5m],
            period=min(20, max(2, len(candles_5m)))
        )
        ema_20_1m = cls.compute_ema(
            [b.close for b in candles],
            period=min(20, max(2, len(candles)))
        )

        # Check CALL
        cond_5m_call = c_5m.is_bullish and (c_5m.close > ema_20_5m)
        cond_1m_bull = (c.is_bullish and prev.is_bearish and
                        c.open <= (prev.close + 1e-5) and
                        c.close >= (prev.open - 1e-5))
        cond_1m_ema_call = c.close > ema_20_1m
        cond_conf_call = c.close > prev.high

        if cond_5m_call and cond_1m_bull and cond_1m_ema_call and cond_conf_call:
            upper_wick_ratio = upper_wick_c / rng_c
            if upper_wick_ratio > 0.30:
                return False, f"Upper wick rejection {upper_wick_ratio*100:.1f}% > 30%", {}

            return True, "BULLISH MTF Engulfing Breakout Confirmed", {
                "direction": "CALL",
                "pattern": "MTF_ENGULFING_1M",
                "expiry_minutes": 2,
                "body_ratio": round(body_ratio, 3),
                "ema_20_1m": round(ema_20_1m, 5),
                "ema_20_5m": round(ema_20_5m, 5),
                "payout_pct": payout_pct,
            }

        # Check PUT
        cond_5m_put = c_5m.is_bearish and (c_5m.close < ema_20_5m)
        cond_1m_bear = (c.is_bearish and prev.is_bullish and
                        c.open >= (prev.close - 1e-5) and
                        c.close <= (prev.open + 1e-5))
        cond_1m_ema_put = c.close < ema_20_1m
        cond_conf_put = c.close < prev.low

        if cond_5m_put and cond_1m_bear and cond_1m_ema_put and cond_conf_put:
            lower_wick_ratio = lower_wick_c / rng_c
            if lower_wick_ratio > 0.30:
                return False, f"Lower wick rejection {lower_wick_ratio*100:.1f}% > 30%", {}

            return True, "BEARISH MTF Engulfing Breakout Confirmed", {
                "direction": "PUT",
                "pattern": "MTF_ENGULFING_1M",
                "expiry_minutes": 2,
                "body_ratio": round(body_ratio, 3),
                "ema_20_1m": round(ema_20_1m, 5),
                "ema_20_5m": round(ema_20_5m, 5),
                "payout_pct": payout_pct,
            }

        return False, "No MTF Engulfing setup confirmed", {}


# ---------------------------------------------------------------------------
# Telegram Direct Sender
# ---------------------------------------------------------------------------

class TelegramSender:
    """Sends signals and screenshots directly to Telegram."""

    def __init__(self, token: str, chat_ids: List[str]):
        self.token = token
        self.chat_ids = list(chat_ids)
        self.api_base = f"https://api.telegram.org/bot{token}"
        self.refresh_subscribers()

    def refresh_subscribers(self):
        """Auto-discover any new subscribers who messaged the bot."""
        try:
            import httpx
            resp = httpx.get(f"{self.api_base}/getUpdates", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("result", []):
                    msg = item.get("message", {}) or item.get("callback_query", {}).get("message", {})
                    chat = msg.get("chat", {})
                    cid = str(chat.get("id", ""))
                    if cid and cid not in self.chat_ids:
                        self.chat_ids.append(cid)
        except Exception:
            pass

    def send_signal_with_screenshot(
        self,
        symbol: str,
        direction: str,
        price: float,
        payout: float,
        details: Dict,
        screenshot_bytes: Optional[bytes] = None,
    ) -> bool:
        """Send a signal alert with chart screenshot to all subscribers."""
        import httpx

        # Refresh subscribers right before dispatching
        self.refresh_subscribers()

        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist_tz).strftime("%H:%M:%S")
        expiry_ist = (datetime.now(ist_tz) + timedelta(minutes=2)).strftime("%H:%M:%S")

        is_call = direction.upper() in ["CALL", "UP", "BUY"]
        dir_badge = "CALL (UP) 🟢" if is_call else "PUT (DOWN) 🔴"
        arrow = "📈" if is_call else "📉"

        body_ratio = details.get("body_ratio", 0.7)
        ema_1m = details.get("ema_20_1m", price)
        ema_5m = details.get("ema_20_5m", price)

        caption = (
            f"🚀 <b>SIGNAL ALERT: STRATEGY 1 (MTF_ENGULFING_1M)</b>\n"
            f"────────────────────────\n"
            f"📊 <b>Asset:</b> <code>{symbol}</code>\n"
            f"💰 <b>OTC Payout:</b> <b>{payout:.0f}%</b>\n"
            f"{arrow} <b>Direction:</b> <b>{dir_badge}</b>\n"
            f"⏱ <b>Chart Timeframe:</b> <b>1 Min</b>\n"
            f"⌛ <b>Expiry Time:</b> <b>2 Mins</b>\n"
            f"🕒 <b>Entry Time:</b> <b>{now_ist} IST</b>\n"
            f"💵 <b>Entry Price:</b> <code>{price}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📐 <b>Body Ratio:</b> {body_ratio*100:.1f}%\n"
            f"📏 <b>EMA 20 (1M):</b> <code>{ema_1m}</code>\n"
            f"📏 <b>EMA 20 (5M):</b> <code>{ema_5m}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ <b>Expiry:</b> <b>{expiry_ist} IST (2 min)</b>\n"
            f"📡 <b>Source:</b> Live Quotex Chart Screenshot\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <b>100% Real Signal from Live Market</b>"
        )

        success = False
        for chat_id in self.chat_ids:
            chat_id = chat_id.strip()
            if not chat_id:
                continue
            try:
                if screenshot_bytes:
                    files = {"photo": ("chart.png", BytesIO(screenshot_bytes), "image/png")}
                    data = {
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                    }
                    resp = httpx.post(
                        f"{self.api_base}/sendPhoto",
                        data=data,
                        files=files,
                        timeout=15,
                    )
                else:
                    resp = httpx.post(
                        f"{self.api_base}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": caption,
                            "parse_mode": "HTML",
                        },
                        timeout=15,
                    )

                if resp.status_code == 200:
                    success = True
            except Exception as e:
                print(f"Telegram send error: {e}")

        return success


# ---------------------------------------------------------------------------
# CDP Client
# ---------------------------------------------------------------------------

class CDPClient:
    """Chrome DevTools Protocol client."""

    def __init__(self, port: int = CDP_PORT):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._ws = None
        self._msg_id = 0

    def is_ready(self) -> bool:
        try:
            import httpx
            resp = httpx.get(f"{self.base_url}/json/version", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def get_browser_info(self) -> Optional[dict]:
        try:
            import httpx
            resp = httpx.get(f"{self.base_url}/json/version", timeout=3)
            return resp.json()
        except Exception:
            return None

    def get_targets(self) -> list:
        try:
            import httpx
            resp = httpx.get(f"{self.base_url}/json", timeout=3)
            return resp.json()
        except Exception:
            return []

    def find_quotex_tab(self) -> Optional[dict]:
        targets = self.get_targets()
        for t in targets:
            url = t.get("url", "")
            if "qxbroker.com" in url or "quotex.io" in url:
                return t
        return None

    def connect_ws(self, ws_url: str) -> bool:
        try:
            import websockets.sync.client as ws_sync
            self._ws = ws_sync.connect(ws_url, max_size=10_000_000)
            return True
        except Exception as e:
            print(f"WebSocket error: {e}")
            return False

    def send_command(self, method: str, params: dict = None) -> dict:
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        self._ws.send(json.dumps(msg))

        deadline = time.time() + 15
        while time.time() < deadline:
            raw = self._ws.recv(timeout=10)
            data = json.loads(raw)
            if data.get("id") == self._msg_id:
                return data
        return {}

    def evaluate_js(self, expression: str):
        try:
            result = self.send_command("Runtime.evaluate", {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            })
            val = result.get("result", {}).get("result", {})
            return val.get("value")
        except Exception:
            return None

    def capture_screenshot(self) -> Optional[bytes]:
        """Capture a full-page screenshot as PNG bytes."""
        try:
            result = self.send_command("Page.captureScreenshot", {
                "format": "png",
                "quality": 90,
            })
            data_b64 = result.get("result", {}).get("data", "")
            if data_b64:
                return base64.b64decode(data_b64)
        except Exception:
            pass
        return None

    def close(self):
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Candle History Manager
# ---------------------------------------------------------------------------

class CandleHistory:
    """Manages per-currency candle history with proper OHLCV accumulation."""

    def __init__(self):
        self._accumulators: Dict[str, dict] = {}
        self._history: Dict[str, List[Candle]] = {}
        self.completed_candles = 0
        self.signals_fired = 0

    def add_tick(self, symbol: str, price: float) -> Optional[Candle]:
        """Add a tick and return a completed candle if minute boundary crossed."""
        now = time.time()
        current_minute = int(now // 60) * 60

        if symbol not in self._history:
            self._history[symbol] = []

        if symbol not in self._accumulators:
            self._accumulators[symbol] = {
                "minute": current_minute,
                "open": price, "high": price,
                "low": price, "close": price, "ticks": 1,
            }
            return None

        acc = self._accumulators[symbol]

        if acc["minute"] == current_minute:
            acc["high"] = max(acc["high"], price)
            acc["low"] = min(acc["low"], price)
            acc["close"] = price
            acc["ticks"] += 1
            return None

        # Minute crossed - emit completed candle
        completed = Candle(
            timestamp=acc["minute"],
            open=acc["open"], high=acc["high"],
            low=acc["low"], close=acc["close"],
            volume=acc["ticks"] * 100,
        )
        self._history[symbol].append(completed)
        # Keep last 100 candles per currency
        if len(self._history[symbol]) > 100:
            self._history[symbol] = self._history[symbol][-100:]

        self.completed_candles += 1

        self._accumulators[symbol] = {
            "minute": current_minute,
            "open": price, "high": price,
            "low": price, "close": price, "ticks": 1,
        }
        return completed

    def get_candles(self, symbol: str) -> List[Candle]:
        """Get all completed candles for a symbol."""
        return self._history.get(symbol, [])

    def get_candle_count(self, symbol: str) -> int:
        return len(self._history.get(symbol, []))


# ---------------------------------------------------------------------------
# Scanner Engine
# ---------------------------------------------------------------------------

class ScannerEngine:
    """Background scanning engine with strategy evaluation and Telegram alerts."""

    JS_READ_PRICE = r"""(() => {
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
    })()"""

    JS_CLICK_TAB = """(() => {{
        const tabs = document.querySelectorAll('.pair-item, .tab-item, .navigation-item, [class*="asset-item"], [class*="pair"]');
        for (const tab of tabs) {{
            const txt = tab.innerText || tab.textContent || '';
            if (txt.includes('{pair_code}')) {{
                tab.click();
                return 'clicked';
            }}
        }}
        const allClickable = document.querySelectorAll('div, span, button, a');
        for (const el of allClickable) {{
            const txt = (el.innerText || '').trim();
            if (txt.includes('{pair_code}') && el.offsetParent !== null) {{
                el.click();
                return 'clicked_alt';
            }}
        }}
        return 'not_found';
    }})()"""

    JS_READ_PAYOUT = r"""(() => {
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
            if (el.children.length === 0) {
                const t = (el.innerText || '').trim();
                const m = t.match(/^(\d{2,3})%$/);
                if (m) return parseInt(m[1]);
            }
        }
        return null;
    })()"""

    def __init__(self, app: 'TradePulseApp'):
        self.app = app
        self.cdp = CDPClient(CDP_PORT)
        self.history = CandleHistory()
        self.strategy = StrategyEvaluator()
        self.telegram = TelegramSender(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS)
        self.running = False
        self.paused = False
        self.chrome_proc = None
        self.thread = None
        self.scan_count = 0
        self.total_ticks = 0
        self.signals_sent = 0
        self.currencies_data: Dict[str, dict] = {}
        self._signal_cooldown: Dict[str, float] = {}  # prevent duplicate signals

    def start(self):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.cdp.close()

    def pause(self):
        self.paused = not self.paused

    def _log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.app.log_queue.append(f"[{timestamp}] [{level}] {msg}")

    def _update_currency(self, symbol: str, price: float, payout: int = None):
        prev = self.currencies_data.get(symbol, {}).get("price", 0)
        direction = "up" if price > prev else ("down" if price < prev else "neutral")
        self.currencies_data[symbol] = {
            "price": price,
            "payout": payout,
            "direction": direction,
            "last_update": time.time(),
            "ticks": self.currencies_data.get(symbol, {}).get("ticks", 0) + 1,
            "candles": self.history.get_candle_count(symbol),
        }

    def _find_chrome(self) -> Optional[str]:
        for p in CHROME_PATHS:
            if os.path.isfile(p):
                return p
        return None

    def _launch_chrome(self) -> bool:
        chrome_exe = self._find_chrome()
        if not chrome_exe:
            self._log("Chrome/Edge not found!", "ERROR")
            return False

        self._log(f"Launching: {chrome_exe}")
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
        self.chrome_proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self._log(f"Chrome PID {self.chrome_proc.pid}")
        return True

    def _check_signal_cooldown(self, symbol: str) -> bool:
        """Prevent duplicate signals within 3 minutes."""
        last = self._signal_cooldown.get(symbol, 0)
        return (time.time() - last) > 180  # 3 minute cooldown

    def _fire_signal(self, symbol: str, price: float, payout: float, details: Dict):
        """Evaluate, screenshot, and send signal to Telegram."""
        if not self._check_signal_cooldown(symbol):
            self._log(f"Signal cooldown active for {symbol}", "INFO")
            return

        direction = details.get("direction", "CALL")
        self._log(f"🚨 SIGNAL DETECTED: {symbol} {direction} @ {price}", "SIGNAL")

        # Wait a moment for chart to render, then capture screenshot
        time.sleep(0.5)
        screenshot = self.cdp.capture_screenshot()

        # Save screenshot locally
        if screenshot:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{symbol.replace('/', '_').replace(' ', '_')}_{direction}_{ts}.png"
            filepath = os.path.join(SCREENSHOTS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(screenshot)
            self._log(f"Screenshot saved: {filename}")

        # Send to Telegram
        success = self.telegram.send_signal_with_screenshot(
            symbol=symbol,
            direction=direction,
            price=price,
            payout=payout,
            details=details,
            screenshot_bytes=screenshot,
        )

        if success:
            self.signals_sent += 1
            self.history.signals_fired += 1
            self._signal_cooldown[symbol] = time.time()
            self._log(f"✅ Signal sent to Telegram! {symbol} {direction}", "SIGNAL")
        else:
            self._log(f"❌ Failed to send Telegram signal for {symbol}", "ERROR")

    def _run(self):
        """Main scanner loop."""
        self._log("Starting scanner engine...")
        self.app.set_status("launching", "Launching Chrome...")

        if not self._launch_chrome():
            self.app.set_status("error", "Chrome not found")
            self.running = False
            return

        self.app.set_status("connecting", "Connecting to Chrome...")
        self._log("Waiting for CDP...")

        for i in range(30):
            if not self.running:
                return
            if self.cdp.is_ready():
                info = self.cdp.get_browser_info()
                browser = info.get("Browser", "Chrome") if info else "Chrome"
                self._log(f"CDP connected: {browser}")
                break
            time.sleep(1)
        else:
            self._log("CDP timeout!", "ERROR")
            self.app.set_status("error", "CDP failed")
            self.running = False
            return

        self.app.set_status("connecting", "Finding Quotex...")
        quotex_tab = None
        for i in range(20):
            if not self.running:
                return
            quotex_tab = self.cdp.find_quotex_tab()
            if quotex_tab:
                break
            self._log(f"Waiting for Quotex tab... ({i + 1})")
            time.sleep(2)

        if not quotex_tab:
            self._log("No Quotex tab! Log into qxbroker.com", "ERROR")
            self.app.set_status("error", "Log into Quotex")
            self.running = False
            return

        ws_url = quotex_tab.get("webSocketDebuggerUrl")
        if not ws_url or not self.cdp.connect_ws(ws_url):
            self._log("WebSocket failed", "ERROR")
            self.app.set_status("error", "WebSocket failed")
            self.running = False
            return

        self.cdp.send_command("Runtime.enable")
        self.cdp.send_command("Page.enable")
        self._log(f"Connected: {quotex_tab.get('title', '')}")
        self.app.set_status("scanning", "Live scanning...")

        time.sleep(3)  # Wait for page to load

        currency_index = 0
        self._log(f"Scanning {len(OTC_CURRENCIES)} currencies...")

        while self.running:
            if self.paused:
                self.app.set_status("paused", "Paused")
                time.sleep(1)
                continue

            currency = OTC_CURRENCIES[currency_index % len(OTC_CURRENCIES)]
            symbol = currency["name"]
            pair_code = currency["code"]
            default_payout = currency["payout"]

            # Click currency tab
            js_click = self.JS_CLICK_TAB.format(pair_code=pair_code)
            self.cdp.evaluate_js(js_click)
            time.sleep(1.2)

            # Read price & payout
            price = self.cdp.evaluate_js(self.JS_READ_PRICE)
            payout = self.cdp.evaluate_js(self.JS_READ_PAYOUT) or default_payout

            if price and price > 0:
                self.scan_count += 1
                self.total_ticks += 1
                self._update_currency(symbol, price, payout)

                self._log(
                    f"#{self.scan_count:<4} {symbol:<20} @ {price:<12.5g}  "
                    f"Payout: {payout}%  Candles: {self.history.get_candle_count(symbol)}"
                )

                # Add tick to history
                completed = self.history.add_tick(symbol, price)

                # If a candle just completed, evaluate strategy
                if completed:
                    candles = self.history.get_candles(symbol)
                    self._log(
                        f"CANDLE {symbol}: O={completed.open:.5g} "
                        f"H={completed.high:.5g} L={completed.low:.5g} "
                        f"C={completed.close:.5g}",
                        "CANDLE"
                    )

                    if len(candles) >= 6:
                        matched, reason, details = self.strategy.evaluate_mtf_engulfing(
                            candles, payout_pct=payout
                        )

                        if matched:
                            self._fire_signal(symbol, price, payout, details)
                        else:
                            self._log(f"Strategy: {reason}")

                self.app.set_status("scanning",
                    f"Scanning {symbol} — {self.scan_count} ticks | "
                    f"{self.signals_sent} signals"
                )

            # Second tick
            time.sleep(1.2)
            price2 = self.cdp.evaluate_js(self.JS_READ_PRICE)
            if price2 and price2 > 0:
                self.total_ticks += 1
                self._update_currency(symbol, price2, payout)
                completed2 = self.history.add_tick(symbol, price2)
                if completed2:
                    candles = self.history.get_candles(symbol)
                    if len(candles) >= 6:
                        matched, reason, details = self.strategy.evaluate_mtf_engulfing(
                            candles, payout_pct=payout
                        )
                        if matched:
                            self._fire_signal(symbol, price2, payout, details)

            currency_index += 1

            if currency_index % len(OTC_CURRENCIES) == 0:
                active = len(self.currencies_data)
                self._log(
                    f"ROTATION #{currency_index // len(OTC_CURRENCIES)} — "
                    f"{active} currencies | {self.total_ticks} ticks | "
                    f"{self.history.completed_candles} candles | "
                    f"{self.signals_sent} signals sent",
                    "SUMMARY"
                )

        self._log("Scanner stopped")
        self.cdp.close()


# ---------------------------------------------------------------------------
# GUI Application
# ---------------------------------------------------------------------------

class TradePulseApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1000x750")
        self.root.minsize(850, 650)
        self.root.configure(bg=COLORS["bg_dark"])

        self.log_queue = []
        self.status_text = "Ready"
        self.status_mode = "idle"
        self.engine = ScannerEngine(self)
        self._start_time = None

        self._build_ui()
        self._start_gui_updater()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # ========== HEADER ==========
        header = tk.Frame(self.root, bg=COLORS["bg_header"], height=75)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg=COLORS["bg_header"])
        title_box.pack(side="left", padx=20, pady=8)

        tk.Label(title_box,
            text="⚡ TradePulse Scanner v2",
            bg=COLORS["bg_header"], fg=COLORS["accent_gold"],
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w")

        tk.Label(title_box,
            text="Self-Contained • Direct-to-Telegram • Real Screenshots",
            bg=COLORS["bg_header"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 9)
        ).pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(header, bg=COLORS["bg_header"])
        btn_frame.pack(side="right", padx=20, pady=15)

        self.btn_start = tk.Button(btn_frame, text="▶  START",
            bg=COLORS["btn_start"], fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat",
            padx=20, pady=6, cursor="hand2", command=self._on_start)
        self.btn_start.pack(side="left", padx=5)

        self.btn_pause = tk.Button(btn_frame, text="⏸  PAUSE",
            bg=COLORS["btn_pause"], fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat",
            padx=15, pady=6, cursor="hand2", state="disabled",
            command=self._on_pause)
        self.btn_pause.pack(side="left", padx=5)

        self.btn_stop = tk.Button(btn_frame, text="⏹  STOP",
            bg=COLORS["btn_stop"], fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat",
            padx=15, pady=6, cursor="hand2", state="disabled",
            command=self._on_stop)
        self.btn_stop.pack(side="left", padx=5)

        # ========== STATUS BAR ==========
        status_bar = tk.Frame(self.root, bg=COLORS["bg_card"], height=32)
        status_bar.pack(fill="x", pady=(0, 1))
        status_bar.pack_propagate(False)

        self.status_dot = tk.Label(status_bar, text="●",
            bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Segoe UI", 12))
        self.status_dot.pack(side="left", padx=(15, 5))

        self.status_label = tk.Label(status_bar,
            text="Ready — Click START to begin",
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 9))
        self.status_label.pack(side="left")

        self.clock_label = tk.Label(status_bar, text="",
            bg=COLORS["bg_card"], fg=COLORS["text_dim"],
            font=("Consolas", 9))
        self.clock_label.pack(side="right", padx=15)

        # ========== STATS ROW ==========
        stats_frame = tk.Frame(self.root, bg=COLORS["bg_dark"])
        stats_frame.pack(fill="x", padx=15, pady=(8, 5))

        self.stat_widgets = {}
        stats = [
            ("currencies", "Currencies", "0/20"),
            ("ticks", "Ticks", "0"),
            ("candles", "Candles", "0"),
            ("signals", "Signals Sent", "0"),
            ("uptime", "Uptime", "00:00"),
            ("telegram", "Telegram", "Ready"),
        ]

        for key, label, default in stats:
            card = tk.Frame(stats_frame, bg=COLORS["bg_card"],
                highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=3)

            val = tk.Label(card, text=default,
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=("Segoe UI", 14, "bold"))
            val.pack(pady=(8, 0))

            tk.Label(card, text=label,
                bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                font=("Segoe UI", 8)).pack(pady=(0, 8))

            self.stat_widgets[key] = val

        # ========== MAIN CONTENT ==========
        content = tk.Frame(self.root, bg=COLORS["bg_dark"])
        content.pack(fill="both", expand=True, padx=15, pady=5)

        # Left: Currency Table
        left = tk.Frame(content, bg=COLORS["bg_card"],
            highlightbackground=COLORS["border"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))

        lheader = tk.Frame(left, bg=COLORS["bg_header"])
        lheader.pack(fill="x")
        tk.Label(lheader, text="  📊 Live Currencies",
            bg=COLORS["bg_header"], fg=COLORS["accent_blue"],
            font=("Segoe UI", 10, "bold")).pack(side="left", pady=6, padx=8)

        # Column headers
        col_hdr = tk.Frame(left, bg=COLORS["bg_dark"])
        col_hdr.pack(fill="x", padx=2)
        for text, w in [("Currency", 17), ("Price", 11), ("Pay", 5), ("Bars", 4), ("Ticks", 5)]:
            tk.Label(col_hdr, text=text, bg=COLORS["bg_dark"],
                fg=COLORS["text_dim"], font=("Segoe UI", 7),
                width=w, anchor="w").pack(side="left", padx=1)

        # Scrollable list
        canvas = tk.Canvas(left, bg=COLORS["bg_card"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        self.currency_frame = tk.Frame(canvas, bg=COLORS["bg_card"])
        self.currency_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.currency_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.currency_rows = {}
        for curr in OTC_CURRENCIES:
            row = tk.Frame(self.currency_frame, bg=COLORS["bg_card"])
            row.pack(fill="x", padx=3, pady=1)

            name = tk.Label(row, text=curr["name"], bg=COLORS["bg_card"],
                fg=COLORS["text_primary"], font=("Consolas", 8), width=19, anchor="w")
            name.pack(side="left", padx=1)

            price = tk.Label(row, text="—", bg=COLORS["bg_card"],
                fg=COLORS["text_dim"], font=("Consolas", 8, "bold"), width=11, anchor="w")
            price.pack(side="left", padx=1)

            pay = tk.Label(row, text="—", bg=COLORS["bg_card"],
                fg=COLORS["text_dim"], font=("Consolas", 8), width=5, anchor="w")
            pay.pack(side="left", padx=1)

            bars = tk.Label(row, text="0", bg=COLORS["bg_card"],
                fg=COLORS["text_dim"], font=("Consolas", 8), width=4, anchor="w")
            bars.pack(side="left", padx=1)

            ticks = tk.Label(row, text="0", bg=COLORS["bg_card"],
                fg=COLORS["text_dim"], font=("Consolas", 8), width=5, anchor="w")
            ticks.pack(side="left", padx=1)

            self.currency_rows[curr["name"]] = {
                "price": price, "payout": pay, "bars": bars, "ticks": ticks,
            }

        # Right: Log
        right = tk.Frame(content, bg=COLORS["bg_card"],
            highlightbackground=COLORS["border"], highlightthickness=1)
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))

        rheader = tk.Frame(right, bg=COLORS["bg_header"])
        rheader.pack(fill="x")
        tk.Label(rheader, text="  📋 Scanner Log",
            bg=COLORS["bg_header"], fg=COLORS["accent_purple"],
            font=("Segoe UI", 10, "bold")).pack(side="left", pady=6, padx=8)

        self.log_text = scrolledtext.ScrolledText(right,
            bg="#0d1117", fg=COLORS["text_secondary"],
            font=("Consolas", 8), wrap="word",
            insertbackground=COLORS["text_primary"],
            selectbackground=COLORS["accent_blue"],
            relief="flat", borderwidth=0)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_text.configure(state="disabled")
        self.log_text.tag_configure("INFO", foreground=COLORS["text_secondary"])
        self.log_text.tag_configure("ERROR", foreground=COLORS["accent_red"])
        self.log_text.tag_configure("CANDLE", foreground=COLORS["accent_green"])
        self.log_text.tag_configure("SIGNAL", foreground=COLORS["accent_gold"])
        self.log_text.tag_configure("SUMMARY", foreground=COLORS["accent_purple"])

        # ========== FOOTER ==========
        footer = tk.Frame(self.root, bg=COLORS["bg_header"], height=25)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        tk.Label(footer,
            text=(f"TradePulse v{APP_VERSION}  •  "
                  f"Bot: @TradePulse_QuotexBot  •  "
                  f"Subscribers: {', '.join(TELEGRAM_CHAT_IDS)}  •  "
                  f"Screenshots: {SCREENSHOTS_DIR}"),
            bg=COLORS["bg_header"], fg=COLORS["text_dim"],
            font=("Segoe UI", 7)).pack(side="left", padx=15)

    # ========== ACTIONS ==========

    def _on_start(self):
        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_stop.configure(state="normal")
        self._start_time = time.time()
        self.engine.start()
        self._append_log("[SYSTEM] Scanner started — Direct-to-Telegram mode", "INFO")

    def _on_pause(self):
        self.engine.pause()
        if self.engine.paused:
            self.btn_pause.configure(text="▶  RESUME", bg=COLORS["btn_start"])
        else:
            self.btn_pause.configure(text="⏸  PAUSE", bg=COLORS["btn_pause"])

    def _on_stop(self):
        self.engine.stop()
        self.btn_start.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="⏸  PAUSE", bg=COLORS["btn_pause"])
        self.btn_stop.configure(state="disabled")
        self.set_status("idle", "Stopped")

    def _on_close(self):
        if self.engine.running:
            self.engine.stop()
        self.root.destroy()

    def set_status(self, mode: str, text: str):
        self.status_mode = mode
        self.status_text = text

    def _append_log(self, msg: str, tag: str = "INFO"):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _start_gui_updater(self):
        self._update_gui()

    def _update_gui(self):
        # Process log queue
        while self.log_queue:
            msg = self.log_queue.pop(0)
            tag = "INFO"
            if "[ERROR]" in msg:
                tag = "ERROR"
            elif "[CANDLE]" in msg:
                tag = "CANDLE"
            elif "[SIGNAL]" in msg:
                tag = "SIGNAL"
            elif "[SUMMARY]" in msg:
                tag = "SUMMARY"
            self._append_log(msg, tag)

        # Status bar
        color_map = {
            "idle": COLORS["text_dim"], "launching": COLORS["accent_blue"],
            "connecting": COLORS["accent_blue"], "scanning": COLORS["accent_green"],
            "paused": COLORS["btn_pause"], "error": COLORS["accent_red"],
        }
        self.status_dot.configure(fg=color_map.get(self.status_mode, COLORS["text_dim"]))
        self.status_label.configure(text=self.status_text)
        self.clock_label.configure(text=datetime.now().strftime("%H:%M:%S"))

        # Stats
        active = len(self.engine.currencies_data)
        total = len(OTC_CURRENCIES)
        self.stat_widgets["currencies"].configure(text=f"{active}/{total}")
        self.stat_widgets["ticks"].configure(text=str(self.engine.total_ticks))
        self.stat_widgets["candles"].configure(
            text=str(self.engine.history.completed_candles))
        self.stat_widgets["signals"].configure(
            text=str(self.engine.signals_sent),
            fg=COLORS["accent_gold"] if self.engine.signals_sent > 0 else COLORS["text_primary"])

        if self._start_time and self.engine.running:
            elapsed = int(time.time() - self._start_time)
            m, s = divmod(elapsed, 60)
            h, m = divmod(m, 60)
            self.stat_widgets["uptime"].configure(
                text=f"{h}h {m}m" if h else f"{m:02d}:{s:02d}")

        # Telegram status
        self.stat_widgets["telegram"].configure(
            text="Active" if self.engine.running else "Ready",
            fg=COLORS["accent_green"] if self.engine.running else COLORS["text_dim"])

        # Currency rows
        for symbol, data in self.engine.currencies_data.items():
            if symbol in self.currency_rows:
                row = self.currency_rows[symbol]
                p = data["price"]
                d = data.get("direction", "neutral")
                payout = data.get("payout")
                ticks = data.get("ticks", 0)
                bars = data.get("candles", 0)

                pc = (COLORS["accent_green"] if d == "up"
                    else COLORS["accent_red"] if d == "down"
                    else COLORS["text_primary"])

                row["price"].configure(text=f"{p:.5g}", fg=pc)
                row["ticks"].configure(text=str(ticks), fg=COLORS["text_secondary"])
                row["bars"].configure(text=str(bars),
                    fg=COLORS["accent_green"] if bars >= 6 else COLORS["text_dim"])

                if payout:
                    payc = (COLORS["accent_green"] if payout >= 85
                        else COLORS["accent_gold"] if payout >= 80
                        else COLORS["accent_red"])
                    row["payout"].configure(text=f"{payout}%", fg=payc)

        self.root.after(200, self._update_gui)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Load .env if available
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

        # Re-read after env load
        token = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
        if token != TELEGRAM_BOT_TOKEN:
            TELEGRAM_BOT_TOKEN_NEW = token

    app = TradePulseApp()
    app.run()
