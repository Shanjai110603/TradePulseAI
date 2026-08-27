import os
import json
import logging
import httpx
from typing import Dict, Any, List, Optional, Union
from app.core.config import settings
from app.telegram.formatter import TelegramMessageFormatter

logger = logging.getLogger(__name__)


def resolve_pattern_image(pattern_name: str, raw_image_path: Optional[str] = None) -> Optional[str]:
    """
    Robustly resolves pattern reference diagram from multiple possible paths
    across local dev, container root /app, and backend mounts.
    """
    search_paths = []
    if raw_image_path:
        clean = raw_image_path.lstrip("/").replace("\\", "/")
        search_paths.extend([
            raw_image_path,
            clean,
            f"/app/{clean}",
            f"/app/backend/{clean}",
            f"backend/{clean}",
        ])

    p_num = None
    p_upper = pattern_name.upper()
    if "15" in p_upper:
        p_num = 15
    elif "14" in p_upper:
        p_num = 14
    elif "1" in p_upper or "SMC" in p_upper:
        p_num = 1

    if p_num:
        search_paths.extend([
            f"uploads/patterns/pattern_type_{p_num}.jpg",
            f"/app/uploads/patterns/pattern_type_{p_num}.jpg",
            f"/app/backend/uploads/patterns/pattern_type_{p_num}.jpg",
            f"backend/uploads/patterns/pattern_type_{p_num}.jpg",
            f"/uploads/patterns/pattern_type_{p_num}.jpg",
            f"./uploads/patterns/pattern_type_{p_num}.jpg",
        ])

    for p in search_paths:
        if p and os.path.exists(p) and os.path.isfile(p):
            return p
    return None


class TelegramBotService:
    """
    Manages Telegram Bot communications, message sending, inline keyboards,
    callback queries, photo attachments with strategy graphs, and local test mock simulations.
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
        """Dispatches concise main signal message with live trade candlestick chart and interactive buttons"""
        text, keyboard = TelegramMessageFormatter.format_main_signal(signal_dict)

        # 1. Determine image to attach (Live Trade Candlestick Chart or Reference Diagram)
        pattern_name = str(signal_dict.get("pattern_name", ""))
        raw_image_path = signal_dict.get("image_path")
        photo_path = None

        if raw_image_path and os.path.exists(raw_image_path) and os.path.isfile(raw_image_path):
            photo_path = raw_image_path
        elif raw_image_path and os.path.exists(raw_image_path.lstrip("/")) and os.path.isfile(raw_image_path.lstrip("/")):
            photo_path = raw_image_path.lstrip("/")
        elif raw_image_path and os.path.exists(f"/app/{raw_image_path.lstrip('/')}") and os.path.isfile(f"/app/{raw_image_path.lstrip('/')}"):
            photo_path = f"/app/{raw_image_path.lstrip('/')}"
        else:
            # Generate trade candlestick chart on the fly if raw trigger candles are present
            raw_candles = signal_dict.get("raw_trigger_candles", [])
            if raw_candles:
                try:
                    from app.engine.charts.chart_generator import TradeChartGenerator
                    from app.engine.market_data.base import Candle
                    c_objects = [Candle(**c) if isinstance(c, dict) else c for c in raw_candles]
                    photo_path = TradeChartGenerator.generate_chart(candles=c_objects, signal_data=signal_dict)
                except Exception as gen_err:
                    logger.debug(f"On-the-fly trade chart generation notice: {gen_err}")

            if not photo_path or not os.path.exists(photo_path):
                photo_path = resolve_pattern_image(pattern_name, raw_image_path)

        # 2. Dispatch Photo with rich caption if photo exists
        if photo_path and os.path.exists(photo_path):
            try:
                logger.info(f"[TELEGRAM] Dispatching trade chart photo ({photo_path}) to chat {chat_id}...")
                res = await self.send_photo(
                    chat_id=chat_id,
                    photo_path=photo_path,
                    caption=text,
                    reply_markup={"inline_keyboard": keyboard}
                )
                if res.get("ok"):
                    return res
                logger.warning(f"send_photo returned not ok: {res}. Falling back to standard message...")
            except Exception as err:
                logger.warning(f"send_photo exception ({err}), falling back to standard message...")

        return await self.send_message(chat_id, text, reply_markup={"inline_keyboard": keyboard})

    async def send_photo(
        self,
        chat_id: int,
        photo_path: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Sends photo with caption and inline keyboard to a Telegram chat"""
        if self.test_mode or not self.base_url:
            self.sent_notifications_log.append({"chat_id": chat_id, "photo": photo_path, "caption": caption})
            return {"ok": True, "result": {"message_id": 999999, "chat": {"id": chat_id}}}

        if not os.path.exists(photo_path):
            return {"ok": False, "error": f"File not found: {photo_path}"}

        url = f"{self.base_url}/sendPhoto"
        data: Dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        try:
            with open(photo_path, "rb") as f:
                file_content = f.read()

            files = {"photo": (os.path.basename(photo_path), file_content, "image/jpeg")}

            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(url, data=data, files=files)
                if resp.status_code == 200:
                    return resp.json()

                # If HTML parse error occurred on caption, retry with stripped plain text
                if caption:
                    clean_caption = caption.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<i>", "").replace("</i>", "")
                    data["caption"] = clean_caption
                    data.pop("parse_mode", None)
                    retry_resp = await client.post(url, data=data, files={"photo": (os.path.basename(photo_path), file_content, "image/jpeg")})
                    if retry_resp.status_code == 200:
                        return retry_resp.json()

                logger.error(f"Telegram sendPhoto failed: {resp.status_code} - {resp.text}")
                return {"ok": False, "error": resp.text}
        except Exception as e:
            logger.error(f"Failed to send Telegram photo to {chat_id}: {e}")
            return {"ok": False, "error": str(e)}

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
