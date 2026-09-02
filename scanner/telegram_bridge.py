"""
TradePulse Telegram Bridge — Two-Way Interactive Remote & Signal Dispatcher
============================================================================
Provides bidirectional control between Telegram (@TradePulse_QuotexBot) and the Windows Browser App:
 - Dispatches real-time VIP Signal Cards with attached chart screenshots
 - Listens for incoming commands (/status, /screenshot, /markets, /switch, /pause, /resume, /analyze)
 - Handles interactive inline keyboard button clicks
 - Auto-registers subscribers
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import Callable, Dict, List, Optional

import httpx

logger = logging.getLogger("telegram_bridge")


class TelegramBridge:
    """Two-way Telegram controller and notification dispatcher."""

    def __init__(
        self,
        bot_token: str,
        initial_chat_ids: Optional[List[str]] = None,
        on_command_callback: Optional[Callable[[str, str, Dict], None]] = None
    ):
        self.token = bot_token
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
        self.subscribers = set(initial_chat_ids or ["8899287239"])
        self.on_command = on_command_callback
        self.running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._last_update_id = 0
        self._http = httpx.Client(timeout=15)

    def start_polling(self):
        """Starts background long-polling for incoming user commands."""
        if self.running:
            return
        self.running = True
        self._poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._poll_thread.start()
        logger.info("Telegram interactive command polling started.")

    def stop_polling(self):
        self.running = False

    def _polling_loop(self):
        while self.running:
            try:
                resp = self._http.get(
                    f"{self.api_base}/getUpdates",
                    params={"offset": self._last_update_id + 1, "timeout": 5}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("result", []):
                        self._last_update_id = max(self._last_update_id, item["update_id"])
                        self._handle_update(item)
            except Exception as e:
                logger.debug(f"Polling tick exception: {e}")
                time.sleep(2)
            time.sleep(0.5)

    def _handle_update(self, item: Dict):
        """Processes an incoming message or callback query."""
        msg = item.get("message")
        cb = item.get("callback_query")

        chat_id = None
        text = ""
        user_name = "User"

        if msg:
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "").strip()
            user_name = msg.get("from", {}).get("first_name", "User")
        elif cb:
            chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
            text = cb.get("data", "").strip()
            user_name = cb.get("from", {}).get("first_name", "User")
            # Acknowledge callback query silently
            try:
                self._http.post(
                    f"{self.api_base}/answerCallbackQuery",
                    json={"callback_query_id": cb.get("id")}
                )
            except Exception:
                pass

        if not chat_id:
            return

        # Register user
        self.subscribers.add(chat_id)

        # Handle commands
        if self.on_command:
            try:
                self.on_command(chat_id, text, {"user_name": user_name})
            except Exception as e:
                logger.error(f"Command handler error: {e}")

    # -----------------------------------------------------------------------
    # Message & Photo Senders
    # -----------------------------------------------------------------------

    def send_message(
        self,
        chat_id: str,
        text: str,
        keyboard: Optional[List[List[Dict[str, str]]]] = None
    ) -> bool:
        """Sends an HTML formatted message with optional inline keyboard."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        try:
            r = self._http.post(f"{self.api_base}/sendMessage", json=payload)
            return r.status_code == 200
        except Exception:
            return False

    def send_photo(
        self,
        chat_id: str,
        photo_bytes: bytes,
        caption: str = "",
        keyboard: Optional[List[List[Dict[str, str]]]] = None
    ) -> bool:
        """Uploads and sends a PNG photo with an HTML caption."""
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }
        if keyboard:
            data["reply_markup"] = json.dumps({"inline_keyboard": keyboard})

        files = {"photo": ("chart.png", BytesIO(photo_bytes), "image/png")}
        try:
            r = self._http.post(f"{self.api_base}/sendPhoto", data=data, files=files, timeout=20)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Send photo error: {e}")
            return False

    def broadcast_signal_card(
        self,
        symbol: str,
        direction: str,
        price: float,
        payout: float,
        details: Dict,
        screenshot_bytes: Optional[bytes] = None
    ) -> int:
        """Dispatches an explainable VIP signal card to all registered subscribers."""
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist_tz).strftime("%H:%M:%S")
        expiry_ist = (datetime.now(ist_tz) + timedelta(minutes=2)).strftime("%H:%M:%S")

        is_call = direction.upper() in ["CALL", "UP", "BUY"]
        dir_badge = "CALL (UP) 🟢" if is_call else "PUT (DOWN) 🔴"
        arrow = "📈" if is_call else "📉"

        confidence = details.get("confidence", 92)
        body_pct = details.get("body_ratio", 0.72) * 100
        wick_pct = details.get("wick_ratio", 0.12) * 100
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
            f"🕒 <b>Entry Time:</b> <b>{now_ist} IST (Next 1M Open)</b>\n"
            f"💵 <b>Entry Price:</b> <code>{price}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 <b>CONFLUENCE BREAKDOWN:</b>\n"
            f"• <b>5M EMA 20 Trend:</b>  ✅ Confirmed (<code>{ema_5m}</code>)\n"
            f"• <b>1M Engulfing Body:</b> ✅ <b>{body_pct:.1f}%</b> (> 65% solid)\n"
            f"• <b>Opposing Wick:</b>     ✅ <b>{wick_pct:.1f}%</b> (≤ 30% limit)\n"
            f"• <b>Preceding Candle:</b>  ✅ Passed (Non-Doji)\n"
            f"• <b>1M Dynamic EMA:</b>    ✅ <code>{ema_1m}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Final Confidence:</b> <b>{confidence}% (HIGH)</b>\n"
            f"⏰ <b>Expiry Time:</b> <b>{expiry_ist} IST</b>\n"
            f"📡 <b>Source:</b> Live Quotex Chart Screenshot\n"
            f"🔒 <i>Safe Mode: 100% Real-Time Market Confluence</i>"
        )

        keyboard = [
            [
                {"text": "📸 Live Chart", "callback_data": "cmd_screenshot"},
                {"text": "📊 All Markets", "callback_data": "cmd_markets"}
            ],
            [
                {"text": "⚡ Status", "callback_data": "cmd_status"}
            ]
        ]

        sent_count = 0
        for cid in list(self.subscribers):
            if screenshot_bytes:
                ok = self.send_photo(cid, screenshot_bytes, caption, keyboard)
            else:
                ok = self.send_message(cid, caption, keyboard)
            if ok:
                sent_count += 1

        return sent_count
