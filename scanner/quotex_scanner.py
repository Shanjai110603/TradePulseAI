"""
TradePulse Quotex Scanner v2.5 — Local AI Browser & Remote Telegram Cockpit
===========================================================================
A unified Windows Desktop Application implementing the Local AI Browser Vision:
 - Dedicated Chromium controller via CDP (undetectable, persistent session)
 - Multi-tier self-healing asset switcher (cycles 20+ OTC currencies)
 - Deterministic Strategy 1 (MTF_ENGULFING_1M) engine with explainability
 - Two-way interactive Telegram remote control (/screenshot, /status, /markets, /switch, /pause, /resume, /analyze)
 - Real-time Quotex chart screenshot capture on signal confluence
 - STRICT SAFE MODE: Zero trade placement capability (observation & research only)
"""

import logging
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Load local modules
try:
    from browser_agent import BrowserAgent
    from strategy_engine import StrategyEngine, Candle
    from telegram_bridge import TelegramBridge
except ImportError:
    from .browser_agent import BrowserAgent
    from .strategy_engine import StrategyEngine, Candle
    from .telegram_bridge import TelegramBridge

# ---------------------------------------------------------------------------
# Load Environment (.env)
# ---------------------------------------------------------------------------

def _load_env():
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

APP_NAME = "TradePulse Quotex Assistant"
APP_VERSION = "2.5.0"

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8928508919:AAH49-CwlHxX7EZnDrMixVUVNsMUCzp56uM"
)
TELEGRAM_CHAT_IDS = [cid.strip() for cid in os.environ.get("TELEGRAM_CHAT_IDS", "8899287239").split(",") if cid.strip()]
SCREENSHOTS_DIR = str(Path.home() / "TradePulseScreenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# 20 Monitored Quotex OTC Currencies
OTC_CURRENCIES = [
    {"name": "EUR/USD (OTC)", "code": "EUR/USD", "payout": 95},
    {"name": "GBP/USD (OTC)", "code": "GBP/USD", "payout": 95},
    {"name": "USD/JPY (OTC)", "code": "USD/JPY", "payout": 82},
    {"name": "AUD/USD (OTC)", "code": "AUD/USD", "payout": 85},
    {"name": "USD/CHF (OTC)", "code": "USD/CHF", "payout": 85},
    {"name": "USD/CAD (OTC)", "code": "USD/CAD", "payout": 85},
    {"name": "NZD/USD (OTC)", "code": "NZD/USD", "payout": 93},
    {"name": "EUR/GBP (OTC)", "code": "EUR/GBP", "payout": 85},
    {"name": "EUR/JPY (OTC)", "code": "EUR/JPY", "payout": 85},
    {"name": "GBP/JPY (OTC)", "code": "GBP/JPY", "payout": 85},
    {"name": "AUD/CAD (OTC)", "code": "AUD/CAD", "payout": 85},
    {"name": "AUD/JPY (OTC)", "code": "AUD/JPY", "payout": 84},
    {"name": "USD/INR (OTC)", "code": "USD/INR", "payout": 88},
    {"name": "USD/BRL (OTC)", "code": "USD/BRL", "payout": 95},
    {"name": "USD/PKR (OTC)", "code": "USD/PKR", "payout": 92},
    {"name": "USD/ZAR (OTC)", "code": "USD/ZAR", "payout": 93},
    {"name": "NZD/CAD (OTC)", "code": "NZD/CAD", "payout": 93},
    {"name": "USD/MXN (OTC)", "code": "USD/MXN", "payout": 85},
    {"name": "USD/TRY (OTC)", "code": "USD/TRY", "payout": 85},
    {"name": "USD/EGP (OTC)", "code": "USD/EGP", "payout": 89},
]

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
# Candle History & Accumulator
# ---------------------------------------------------------------------------

class CandleBuffer:
    """Accumulates price ticks into 1-minute OHLCV candles."""

    def __init__(self):
        self._accumulators: Dict[str, dict] = {}
        self._candles: Dict[str, List[Candle]] = {}
        self.completed_count = 0

    def add_tick(self, symbol: str, price: float) -> Optional[Candle]:
        now = time.time()
        minute = int(now // 60) * 60

        if symbol not in self._candles:
            self._candles[symbol] = []

        if symbol not in self._accumulators:
            self._accumulators[symbol] = {
                "minute": minute,
                "open": price, "high": price,
                "low": price, "close": price, "ticks": 1
            }
            return None

        acc = self._accumulators[symbol]

        # Current minute tick update
        if acc["minute"] == minute:
            acc["high"] = max(acc["high"], price)
            acc["low"] = min(acc["low"], price)
            acc["close"] = price
            acc["ticks"] += 1
            return None

        # Minute rollover: emit completed candle
        completed = Candle(
            timestamp=acc["minute"],
            open=acc["open"],
            high=acc["high"],
            low=acc["low"],
            close=acc["close"],
            volume=acc["ticks"] * 100.0
        )
        self._candles[symbol].append(completed)
        if len(self._candles[symbol]) > 100:
            self._candles[symbol] = self._candles[symbol][-100:]

        self.completed_count += 1

        self._accumulators[symbol] = {
            "minute": minute,
            "open": price, "high": price,
            "low": price, "close": price, "ticks": 1
        }
        return completed

    def get_candles(self, symbol: str) -> List[Candle]:
        return self._candles.get(symbol, [])


# ---------------------------------------------------------------------------
# Assistant Orchestrator Engine
# ---------------------------------------------------------------------------

class AssistantOrchestrator:
    """Coordinates Browser Agent, Strategy Engine, and Telegram Remote."""

    def __init__(self, app: 'TradePulseGUI'):
        self.app = app
        self.browser = BrowserAgent()
        self.strategy = StrategyEngine()
        self.buffer = CandleBuffer()
        self.telegram = TelegramBridge(
            bot_token=TELEGRAM_BOT_TOKEN,
            initial_chat_ids=TELEGRAM_CHAT_IDS,
            on_command_callback=self._handle_telegram_command
        )
        self.running = False
        self.paused = False
        self.worker_thread: Optional[threading.Thread] = None

        self.scan_count = 0
        self.total_ticks = 0
        self.signals_count = 0
        self.currencies_data: Dict[str, dict] = {}
        self._cooldowns: Dict[str, float] = {}

    def start(self):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.telegram.start_polling()
        self.worker_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        self.telegram.stop_polling()
        self.browser.close()

    def pause(self):
        self.paused = not self.paused

    def _log(self, msg: str, tag: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.app.log_queue.append(f"[{ts}] [{tag}] {msg}")

    # -----------------------------------------------------------------------
    # Telegram Remote Command Router
    # -----------------------------------------------------------------------

    def _handle_telegram_command(self, chat_id: str, command: str, meta: Dict):
        """Processes two-way commands from Telegram."""
        user = meta.get("user_name", "User")
        cmd_clean = command.strip()
        cmd_lower = cmd_clean.lower()

        self._log(f"Telegram remote command from {user}: '{cmd_clean}'", "TELEGRAM")

        # 1. /start or help
        if cmd_lower in ["/start", "/help", "cmd_help"]:
            reply = (
                f"👋 <b>Welcome, {user}!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>TradePulse Quotex Assistant Remote</b>\n"
                f"You have direct two-way control over the local Windows browser:\n\n"
                f"• 📸 <b>/screenshot</b> — Instant live Quotex chart photo\n"
                f"• ⚡ <b>/status</b> — Real-time scanner telemetry\n"
                f"• 📊 <b>/markets</b> — Live rates of all 20 OTC pairs\n"
                f"• 🔄 <b>/switch &lt;pair&gt;</b> — Change active chart (e.g. <code>/switch EUR/USD</code>)\n"
                f"• ⏸ <b>/pause</b> &amp; ▶ <b>/resume</b> — Remote scanner control\n"
                f"• 🧠 <b>/analyze</b> — Confluence evaluation on current chart\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔒 <i>Safe Mode: 100% Real Signals, Zero Execution</i>"
            )
            kb = [
                [{"text": "📸 Live Screenshot", "callback_data": "cmd_screenshot"}, {"text": "⚡ Status", "callback_data": "cmd_status"}],
                [{"text": "📊 All Markets", "callback_data": "cmd_markets"}, {"text": "🧠 Analyze Chart", "callback_data": "cmd_analyze"}],
                [{"text": "⏸ Toggle Pause", "callback_data": "cmd_pause"}]
            ]
            self.telegram.send_message(chat_id, reply, kb)

        # 2. /screenshot
        elif cmd_lower in ["/screenshot", "/snap", "cmd_screenshot", "📸 live screenshot"]:
            self.telegram.send_message(chat_id, "📸 <i>Capturing live Quotex chart...</i>")
            screenshot = self.browser.capture_screenshot()
            if screenshot:
                active = self.browser.active_pair
                price = self.browser.read_live_price() or 0.0
                payout = self.browser.read_payout() or 90
                now_str = datetime.now().strftime("%H:%M:%S")
                caption = (
                    f"📸 <b>LIVE QUOTEX CHART SNAPSHOT</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 <b>Pair:</b> <code>{active}</code>\n"
                    f"💵 <b>Price:</b> <code>{price}</code> | <b>Payout:</b> <b>{payout}%</b>\n"
                    f"⏰ <b>Captured:</b> <code>{now_str}</code>\n"
                    f"🔒 <i>Real Browser View (CDP Full Canvas)</i>"
                )
                self.telegram.send_photo(chat_id, screenshot, caption)
                self._log(f"Live chart screenshot delivered to {user}", "TELEGRAM")
            else:
                self.telegram.send_message(chat_id, "⚠️ <i>Could not capture screenshot. Check if browser is connected.</i>")

        # 3. /status
        elif cmd_lower in ["/status", "cmd_status", "⚡ status"]:
            state = "⏸ PAUSED" if self.paused else ("🟢 SCANNING" if self.running else "⏹ STOPPED")
            active_pair = self.browser.active_pair
            candle_count = self.buffer.completed_count
            pairs_count = len(self.currencies_data)
            reply = (
                f"⚡ <b>TRADEPULSE ASSISTANT STATUS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Status:</b> <b>{state}</b>\n"
                f"• <b>Active Pair:</b> <code>{active_pair}</code>\n"
                f"• <b>Monitored Pairs:</b> <code>{pairs_count}/20</code>\n"
                f"• <b>Total Ticks:</b> <code>{self.total_ticks}</code>\n"
                f"• <b>1M Candles Built:</b> <code>{candle_count}</code>\n"
                f"• <b>VIP Signals Fired:</b> <code>{self.signals_count}</code>\n"
                f"• <b>Active Strategy:</b> <b>MTF_ENGULFING_1M (2 Min Expiry)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔒 <i>Safe Mode Active — 24/7 Observation</i>"
            )
            self.telegram.send_message(chat_id, reply)

        # 4. /markets
        elif cmd_lower in ["/markets", "cmd_markets", "📊 all markets"]:
            lines = ["📊 <b>QUOTEX OTC LIVE MARKET RATES</b>\n━━━━━━━━━━━━━━━━━━━━"]
            for curr in OTC_CURRENCIES:
                name = curr["name"]
                data = self.currencies_data.get(name, {})
                price = data.get("price", 0.0)
                payout = data.get("payout", curr["payout"])
                price_str = f"{price:.5g}" if price > 0 else "—"
                lines.append(f"• <b>{name:<15}</b> ➔ <code>{price_str}</code> (<b>{payout}%</b>)")
            lines.append("━━━━━━━━━━━━━━━━━━━━\n<i>Use /switch &lt;pair&gt; to navigate immediately.</i>")
            self.telegram.send_message(chat_id, "\n".join(lines))

        # 5. /switch <symbol>
        elif cmd_lower.startswith("/switch"):
            parts = cmd_clean.split(maxsplit=1)
            if len(parts) > 1:
                target = parts[1].strip()
                self.telegram.send_message(chat_id, f"🔄 <i>Switching browser chart to {target}...</i>")
                ok = self.browser.switch_pair(target)
                if ok:
                    self.telegram.send_message(chat_id, f"✅ <i>Successfully switched to <b>{target}</b>!</i>")
                    self._log(f"Browser switched to {target} via Telegram", "TELEGRAM")
                else:
                    self.telegram.send_message(chat_id, f"⚠️ <i>Failed to switch to {target}. Check tab name.</i>")
            else:
                self.telegram.send_message(chat_id, "Usage: <code>/switch EUR/USD</code>")

        # 6. /pause & /resume
        elif cmd_lower in ["/pause", "cmd_pause"]:
            self.pause()
            txt = "⏸ <i>Scanner paused remotely.</i>" if self.paused else "▶ <i>Scanner resumed remotely.</i>"
            self.telegram.send_message(chat_id, txt)

        elif cmd_lower in ["/resume", "cmd_resume"]:
            self.paused = False
            self.telegram.send_message(chat_id, "▶ <i>Scanner resumed remotely.</i>")

        # 7. /analyze
        elif cmd_lower in ["/analyze", "cmd_analyze", "🧠 analyze chart"]:
            active = self.browser.active_pair
            candles = self.buffer.get_candles(active)
            payout = self.browser.read_payout() or 85
            if len(candles) < 6:
                self.telegram.send_message(
                    chat_id,
                    f"⚠️ <i>Insufficient candle history for <b>{active}</b> ({len(candles)}/6). Allow scanner to observe for 2 minutes.</i>"
                )
            else:
                matched, reason, details = self.strategy.evaluate_mtf_engulfing(candles, payout_pct=payout)
                bd = details.get("breakdown", {})
                reply = (
                    f"🧠 <b>MULTI-FACTOR ANALYSIS: {active}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Setup Status:</b> <b>{'CONFIRMED 🟢' if matched else 'SEARCHING 🔍'}</b>\n"
                    f"• <b>Reason:</b> {reason}\n"
                    f"• <b>Payout Filter:</b> {'✅' if bd.get('payout_check') else '❌'}\n"
                    f"• <b>Doji Check:</b> {'✅' if bd.get('doji_check') else '❌'}\n"
                    f"• <b>Body Ratio (>65%):</b> {'✅' if bd.get('body_ratio_check') else '❌'}\n"
                    f"• <b>Wick Limit (<=30%):</b> {'✅' if bd.get('wick_check') else '❌'}\n"
                    f"• <b>5M EMA20 Trend:</b> {'✅' if bd.get('trend_5m_check') else '❌'}\n"
                    f"• <b>1M Engulfing:</b> {'✅' if bd.get('engulfing_1m_check') else '❌'}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 <b>Confluence Score:</b> <b>{details.get('confidence', 0)}%</b>"
                )
                self.telegram.send_message(chat_id, reply)

    # -----------------------------------------------------------------------
    # Main Scanning Loop
    # -----------------------------------------------------------------------

    def _scan_loop(self):
        self._log("Initializing Local AI Browser Agent...", "BROWSER")
        self.app.set_status("launching", "Launching Chrome via CDP...")

        if not self.browser.launch():
            self.app.set_status("error", "No Chromium browser found")
            self.running = False
            return

        self.app.set_status("connecting", "Connecting to Quotex...")
        self._log("Connecting to browser session...", "BROWSER")

        if not self.browser.connect(timeout=35):
            self._log("Could not connect to Quotex tab. Please log into qxbroker.com", "ERROR")
            self.app.set_status("error", "Log into Quotex in Chrome")
            self.running = False
            return

        self._log("Browser connected. Safe mode engaged.", "BROWSER")
        self.app.set_status("scanning", "Scanning 20 OTC currencies...")

        curr_idx = 0
        while self.running:
            if self.paused:
                self.app.set_status("paused", "Scanner Paused")
                time.sleep(1)
                continue

            curr = OTC_CURRENCIES[curr_idx % len(OTC_CURRENCIES)]
            symbol = curr["name"]

            # Switch chart tab
            self.browser.switch_pair(symbol)
            time.sleep(1.0)

            # Read live price and payout
            price = self.browser.read_live_price()
            payout = self.browser.read_payout() or curr["payout"]

            if price and price > 0:
                self.scan_count += 1
                self.total_ticks += 1

                # Update currencies table data
                prev_p = self.currencies_data.get(symbol, {}).get("price", 0)
                direction = "up" if price > prev_p else ("down" if price < prev_p else "neutral")
                self.currencies_data[symbol] = {
                    "price": price,
                    "payout": payout,
                    "direction": direction,
                    "ticks": self.currencies_data.get(symbol, {}).get("ticks", 0) + 1,
                    "candles": len(self.buffer.get_candles(symbol))
                }

                self._log(f"#{self.scan_count:<4} {symbol:<18} @ {price:<12.5g} Payout: {payout}%")

                # Accumulate candle
                completed_bar = self.buffer.add_tick(symbol, price)
                if completed_bar:
                    candles = self.buffer.get_candles(symbol)
                    self._log(
                        f"1M BAR [{symbol}]: O={completed_bar.open:.5g} "
                        f"H={completed_bar.high:.5g} L={completed_bar.low:.5g} "
                        f"C={completed_bar.close:.5g}",
                        "CANDLE"
                    )

                    # Strategy Confluence Evaluation
                    if len(candles) >= 6:
                        matched, reason, details = self.strategy.evaluate_mtf_engulfing(candles, payout_pct=payout)
                        if matched:
                            self._trigger_signal(symbol, price, payout, details)

                self.app.set_status("scanning", f"Monitoring {symbol} — {self.total_ticks} ticks")

            # Second tick before switching
            time.sleep(1.2)
            price2 = self.browser.read_live_price()
            if price2 and price2 > 0:
                self.total_ticks += 1
                self.buffer.add_tick(symbol, price2)

            curr_idx += 1

            if curr_idx % len(OTC_CURRENCIES) == 0:
                self._log(
                    f"FULL CYCLE COMPLETE — {len(self.currencies_data)} pairs active | "
                    f"{self.total_ticks} ticks | {self.signals_count} signals sent",
                    "SUMMARY"
                )

    def _trigger_signal(self, symbol: str, price: float, payout: float, details: Dict):
        """Fires signal alert, captures live chart photo, and dispatches to Telegram."""
        # 3-minute cooldown per pair
        last_sig = self._cooldowns.get(symbol, 0)
        if (time.time() - last_sig) < 180:
            return

        direction = details.get("direction", "CALL")
        self._log(f"🔥 CONFLUENCE CONFIRMED: {symbol} {direction} @ {price}", "SIGNAL")

        time.sleep(0.4)
        screenshot = self.browser.capture_screenshot()

        # Save locally
        if screenshot:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{symbol.replace('/', '_').replace(' ', '_')}_{direction}_{ts}.png"
            path = os.path.join(SCREENSHOTS_DIR, filename)
            try:
                with open(path, "wb") as f:
                    f.write(screenshot)
                self._log(f"Saved chart screenshot: {filename}")
            except Exception:
                pass

        # Dispatch via Telegram Bridge
        sent = self.telegram.broadcast_signal_card(
            symbol=symbol,
            direction=direction,
            price=price,
            payout=payout,
            details=details,
            screenshot_bytes=screenshot
        )

        if sent > 0:
            self.signals_count += 1
            self._cooldowns[symbol] = time.time()
            self._log(f"Signal card dispatched to {sent} Telegram subscribers!", "SIGNAL")


# ---------------------------------------------------------------------------
# Windows Desktop GUI Cockpit
# ---------------------------------------------------------------------------

class TradePulseGUI:
    """Dark-themed desktop control panel."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION} (Safe Mode)")
        self.root.geometry("1020x760")
        self.root.minsize(850, 650)
        self.root.configure(bg=COLORS["bg_dark"])

        self.log_queue: List[str] = []
        self.status_mode = "idle"
        self.status_text = "Ready"
        self.engine = AssistantOrchestrator(self)
        self._start_time = None

        self._build_interface()
        self._start_gui_loop()
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)

    def _build_interface(self):
        # ========== HEADER ==========
        header = tk.Frame(self.root, bg=COLORS["bg_header"], height=75)
        header.pack(fill="x")
        header.pack_propagate(False)

        tb = tk.Frame(header, bg=COLORS["bg_header"])
        tb.pack(side="left", padx=20, pady=8)

        tk.Label(
            tb, text="⚡ TradePulse Browser Assistant",
            bg=COLORS["bg_header"], fg=COLORS["accent_gold"],
            font=("Segoe UI", 17, "bold")
        ).pack(anchor="w")

        tk.Label(
            tb, text="Local AI Chromium Controller  •  Interactive Telegram Remote  •  Safe Mode",
            bg=COLORS["bg_header"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        # Controls
        bf = tk.Frame(header, bg=COLORS["bg_header"])
        bf.pack(side="right", padx=20, pady=15)

        self.btn_start = tk.Button(
            bf, text="▶  START SCANNER", bg=COLORS["btn_start"], fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=6,
            cursor="hand2", command=self._cmd_start
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_pause = tk.Button(
            bf, text="⏸  PAUSE", bg=COLORS["btn_pause"], fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6,
            cursor="hand2", state="disabled", command=self._cmd_pause
        )
        self.btn_pause.pack(side="left", padx=4)

        self.btn_stop = tk.Button(
            bf, text="⏹  STOP", bg=COLORS["btn_stop"], fg="white",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6,
            cursor="hand2", state="disabled", command=self._cmd_stop
        )
        self.btn_stop.pack(side="left", padx=4)

        # ========== STATUS BAR ==========
        sb = tk.Frame(self.root, bg=COLORS["bg_card"], height=32)
        sb.pack(fill="x", pady=(0, 1))
        sb.pack_propagate(False)

        self.dot = tk.Label(sb, text="●", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Segoe UI", 12))
        self.dot.pack(side="left", padx=(15, 5))

        self.lbl_status = tk.Label(sb, text="Ready — Click START SCANNER to begin", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 9))
        self.lbl_status.pack(side="left")

        self.lbl_clock = tk.Label(sb, text="", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Consolas", 9))
        self.lbl_clock.pack(side="right", padx=15)

        # ========== STATS ROW ==========
        sf = tk.Frame(self.root, bg=COLORS["bg_dark"])
        sf.pack(fill="x", padx=15, pady=(8, 4))

        self.stat_boxes = {}
        items = [
            ("pairs", "Currencies", "0/20"),
            ("ticks", "Total Ticks", "0"),
            ("candles", "1M Candles", "0"),
            ("signals", "Signals Fired", "0"),
            ("uptime", "Uptime", "00:00"),
            ("remote", "Telegram Remote", "Active"),
        ]

        for k, label, dflt in items:
            card = tk.Frame(sf, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=3)
            val = tk.Label(card, text=dflt, bg=COLORS["bg_card"], fg=COLORS["text_primary"], font=("Segoe UI", 13, "bold"))
            val.pack(pady=(6, 0))
            tk.Label(card, text=label, bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).pack(pady=(0, 6))
            self.stat_boxes[k] = val

        # ========== MAIN CONTENT ==========
        main_frame = tk.Frame(self.root, bg=COLORS["bg_dark"])
        main_frame.pack(fill="both", expand=True, padx=15, pady=4)

        # Left: Currencies Table
        left = tk.Frame(main_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        lh = tk.Frame(left, bg=COLORS["bg_header"])
        lh.pack(fill="x")
        tk.Label(lh, text="  📊 Live Monitored Pairs", bg=COLORS["bg_header"], fg=COLORS["accent_blue"], font=("Segoe UI", 9, "bold")).pack(side="left", pady=5, padx=8)

        # Table header
        th = tk.Frame(left, bg=COLORS["bg_dark"])
        th.pack(fill="x", padx=2)
        for t, w in [("Currency", 17), ("Price", 11), ("Pay", 5), ("Bars", 4), ("Ticks", 5)]:
            tk.Label(th, text=t, bg=COLORS["bg_dark"], fg=COLORS["text_dim"], font=("Segoe UI", 7), width=w, anchor="w").pack(side="left", padx=1)

        canvas = tk.Canvas(left, bg=COLORS["bg_card"], highlightthickness=0)
        scroller = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        self.rows_frame = tk.Frame(canvas, bg=COLORS["bg_card"])
        self.rows_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroller.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroller.pack(side="right", fill="y")

        self.rows = {}
        for c in OTC_CURRENCIES:
            rf = tk.Frame(self.rows_frame, bg=COLORS["bg_card"])
            rf.pack(fill="x", padx=3, pady=1)

            name = tk.Label(rf, text=c["name"], bg=COLORS["bg_card"], fg=COLORS["text_primary"], font=("Consolas", 8), width=18, anchor="w")
            name.pack(side="left", padx=1)

            price = tk.Label(rf, text="—", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Consolas", 8, "bold"), width=11, anchor="w")
            price.pack(side="left", padx=1)

            payout = tk.Label(rf, text=f"{c['payout']}%", bg=COLORS["bg_card"], fg=COLORS["accent_green"], font=("Consolas", 8), width=5, anchor="w")
            payout.pack(side="left", padx=1)

            bars = tk.Label(rf, text="0", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Consolas", 8), width=4, anchor="w")
            bars.pack(side="left", padx=1)

            ticks = tk.Label(rf, text="0", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Consolas", 8), width=5, anchor="w")
            ticks.pack(side="left", padx=1)

            self.rows[c["name"]] = {"price": price, "payout": payout, "bars": bars, "ticks": ticks}

        # Right: Log Viewer
        right = tk.Frame(main_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        rh = tk.Frame(right, bg=COLORS["bg_header"])
        rh.pack(fill="x")
        tk.Label(rh, text="  📋 Real-Time Activity Log", bg=COLORS["bg_header"], fg=COLORS["accent_purple"], font=("Segoe UI", 9, "bold")).pack(side="left", pady=5, padx=8)

        self.txt_log = scrolledtext.ScrolledText(
            right, bg="#0d1117", fg=COLORS["text_secondary"], font=("Consolas", 8),
            wrap="word", insertbackground=COLORS["text_primary"],
            selectbackground=COLORS["accent_blue"], relief="flat", borderwidth=0
        )
        self.txt_log.pack(fill="both", expand=True, padx=4, pady=4)
        self.txt_log.configure(state="disabled")

        self.txt_log.tag_configure("INFO", foreground=COLORS["text_secondary"])
        self.txt_log.tag_configure("ERROR", foreground=COLORS["accent_red"])
        self.txt_log.tag_configure("CANDLE", foreground=COLORS["accent_green"])
        self.txt_log.tag_configure("SIGNAL", foreground=COLORS["accent_gold"])
        self.txt_log.tag_configure("TELEGRAM", foreground=COLORS["accent_blue"])
        self.txt_log.tag_configure("SUMMARY", foreground=COLORS["accent_purple"])

        # ========== FOOTER ==========
        ft = tk.Frame(self.root, bg=COLORS["bg_header"], height=24)
        ft.pack(fill="x", side="bottom")
        ft.pack_propagate(False)

        tk.Label(
            ft, text=f"TradePulse AI • Bot: @TradePulse_QuotexBot • Screenshots: {SCREENSHOTS_DIR} • SAFE MODE ACTIVE",
            bg=COLORS["bg_header"], fg=COLORS["text_dim"], font=("Segoe UI", 7)
        ).pack(side="left", padx=15)

    def _cmd_start(self):
        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_stop.configure(state="normal")
        self._start_time = time.time()
        self.engine.start()
        self._append_log("[SYSTEM] Assistant Engine Activated.", "INFO")

    def _cmd_pause(self):
        self.engine.pause()
        if self.engine.paused:
            self.btn_pause.configure(text="▶  RESUME", bg=COLORS["btn_start"])
        else:
            self.btn_pause.configure(text="⏸  PAUSE", bg=COLORS["btn_pause"])

    def _cmd_stop(self):
        self.engine.stop()
        self.btn_start.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="⏸  PAUSE", bg=COLORS["btn_pause"])
        self.btn_stop.configure(state="disabled")
        self.set_status("idle", "Stopped")

    def _on_exit(self):
        if self.engine.running:
            self.engine.stop()
        self.root.destroy()

    def set_status(self, mode: str, text: str):
        self.status_mode = mode
        self.status_text = text

    def _append_log(self, msg: str, tag: str = "INFO"):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", msg + "\n", tag)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _start_gui_loop(self):
        self._tick()

    def _tick(self):
        # Drain log queue
        while self.log_queue:
            msg = self.log_queue.pop(0)
            tag = "INFO"
            if "[ERROR]" in msg:
                tag = "ERROR"
            elif "[CANDLE]" in msg:
                tag = "CANDLE"
            elif "[SIGNAL]" in msg:
                tag = "SIGNAL"
            elif "[TELEGRAM]" in msg:
                tag = "TELEGRAM"
            elif "[SUMMARY]" in msg:
                tag = "SUMMARY"
            self._append_log(msg, tag)

        # Update status bar
        colors = {
            "idle": COLORS["text_dim"],
            "launching": COLORS["accent_blue"],
            "connecting": COLORS["accent_blue"],
            "scanning": COLORS["accent_green"],
            "paused": COLORS["btn_pause"],
            "error": COLORS["accent_red"],
        }
        self.dot.configure(fg=colors.get(self.status_mode, COLORS["text_dim"]))
        self.lbl_status.configure(text=self.status_text)
        self.lbl_clock.configure(text=datetime.now().strftime("%H:%M:%S"))

        # Update stats
        active_count = len(self.engine.currencies_data)
        self.stat_boxes["pairs"].configure(text=f"{active_count}/20")
        self.stat_boxes["ticks"].configure(text=str(self.engine.total_ticks))
        self.stat_boxes["candles"].configure(text=str(self.engine.buffer.completed_count))
        self.stat_boxes["signals"].configure(
            text=str(self.engine.signals_count),
            fg=COLORS["accent_gold"] if self.engine.signals_count > 0 else COLORS["text_primary"]
        )

        if self._start_time and self.engine.running:
            el = int(time.time() - self._start_time)
            m, s = divmod(el, 60)
            h, m = divmod(m, 60)
            self.stat_boxes["uptime"].configure(text=f"{h}h {m}m" if h else f"{m:02d}:{s:02d}")

        # Update currency rows
        for symbol, d in self.engine.currencies_data.items():
            if symbol in self.rows:
                r = self.rows[symbol]
                p = d["price"]
                direction = d.get("direction", "neutral")
                ticks = d.get("ticks", 0)
                bars = d.get("candles", 0)

                col = (COLORS["accent_green"] if direction == "up"
                       else COLORS["accent_red"] if direction == "down"
                       else COLORS["text_primary"])
                r["price"].configure(text=f"{p:.5g}", fg=col)
                r["ticks"].configure(text=str(ticks), fg=COLORS["text_secondary"])
                r["bars"].configure(text=str(bars), fg=COLORS["accent_green"] if bars >= 6 else COLORS["text_dim"])

        self.root.after(200, self._tick)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = TradePulseGUI()
    app.run()
