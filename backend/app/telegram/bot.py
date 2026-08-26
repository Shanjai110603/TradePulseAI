import logging
import httpx
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.telegram.formatter import TelegramMessageFormatter

logger = logging.getLogger(__name__)


class TelegramBotService:
    """
    Manages Telegram Bot communications, message sending, inline keyboards,
    callback queries, and local test mock simulations.
    """

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.test_mode = settings.TELEGRAM_TEST_MODE or not self.bot_token
        self.sent_notifications_log: List[Dict[str, Any]] = []

    async def send_signal_notification(
        self,
        chat_id: int,
        signal_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatches concise main signal message with inline buttons"""
        text, keyboard = TelegramMessageFormatter.format_main_signal(signal_dict)
        return await self.send_message(chat_id, text, reply_markup={"inline_keyboard": keyboard})

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Sends message to a Telegram chat, with local test fallback"""
        msg_payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            msg_payload["parse_mode"] = parse_mode
        if reply_markup:
            msg_payload["reply_markup"] = reply_markup

        # Log for audit and local test mode
        self.sent_notifications_log.append(msg_payload)
        logger.info(f"[TELEGRAM DISPATCH] To: {chat_id} | Text: {text[:60]}...")

        if self.test_mode or not self.base_url:
            return {"ok": True, "result": {"message_id": 999999, "chat": {"id": chat_id}, "text": text}}

        url = f"{self.base_url}/sendMessage"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=msg_payload)
                if resp.status_code == 200:
                    return resp.json()

                # If HTML/markup fails, fallback to clean plain text without markup
                logger.warning(f"Telegram sendMessage returned {resp.status_code}: {resp.text}. Retrying with plain text fallback...")
                clean_text = text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<i>", "").replace("</i>", "")
                fallback_payload: Dict[str, Any] = {
                    "chat_id": chat_id,
                    "text": clean_text
                }
                if reply_markup:
                    fallback_payload["reply_markup"] = reply_markup

                fallback_resp = await client.post(url, json=fallback_payload)
                if fallback_resp.status_code == 200:
                    return fallback_resp.json()

                # Final fallback without any markup at all
                final_payload = {"chat_id": chat_id, "text": clean_text}
                final_resp = await client.post(url, json=final_payload)
                final_resp.raise_for_status()
                return final_resp.json()
            except Exception as e:
                logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
                return {"ok": False, "error": str(e)}

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Edits an existing Telegram message in-place for fast, smooth sub-views"""
        msg_payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            msg_payload["parse_mode"] = parse_mode
        if reply_markup:
            msg_payload["reply_markup"] = reply_markup

        if self.test_mode or not self.base_url:
            return {"ok": True, "result": {"message_id": message_id, "text": text}}

        url = f"{self.base_url}/editMessageText"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=msg_payload)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(f"Failed to edit Telegram message: {e}")
                return {"ok": False, "error": str(e)}

    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> Dict[str, Any]:
        if self.test_mode or not self.base_url:
            return {"ok": True}

        url = f"{self.base_url}/answerCallbackQuery"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(url, json={"callback_query_id": callback_query_id, "text": text})
                return resp.json()
            except Exception as e:
                logger.error(f"Failed to answer callback: {e}")
                return {"ok": False, "error": str(e)}


telegram_service = TelegramBotService()
