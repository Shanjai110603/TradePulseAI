"""
TradePulse Multi-Recipient Telegram Client & Command Poller
Dispatches VIP signal cards with attached HD chart photos to personal chats and VIP channels,
broadcasts automated trade outcome alerts, and listens for interactive remote commands.
"""
import asyncio
import json
import logging
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Set

import httpx
from core.config import settings
from core.models.signal import Signal
from core.telegram.formatter import TelegramFormatter

logger = logging.getLogger(__name__)


class TelegramBridge:
    """Two-way Telegram controller and multi-recipient notification dispatcher."""

    def __init__(
        self,
        token: Optional[str] = None,
        chat_ids: Optional[List[str]] = None,
        admin_chat_ids: Optional[Set[str]] = None,
        on_command_callback: Optional[Callable[[str, str, Dict], None]] = None,
        manager: Optional[Any] = None,
        max_users: Optional[int] = None
    ):
        self.manager = manager
        self.max_users = max_users
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.api_base = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.subscribers: Set[str] = set(chat_ids or settings.chat_id_list)
        if self.max_users and len(self.subscribers) > self.max_users:
            self.subscribers = set(list(self.subscribers)[:self.max_users])
        self.admin_chat_ids: Set[str] = set(admin_chat_ids) if admin_chat_ids is not None else set(settings.admin_chat_id_list)
        self.on_command = on_command_callback

        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._last_update_id = 0
        self._http: Optional[httpx.AsyncClient] = None

    def get_target_chats(self) -> List[str]:
        """
        Resolves active recipient chat/channel IDs respecting the subscriber quota.
        
        Enforces:
        - If `max_users` is specified (e.g., 5 users for Personal Edition),
          the list of broadcast destinations is sliced to strictly prevent exceeding the quota.
        """
        if self.manager:
            active = self.manager.get_active_channel_ids()
            if active:
                return active[:self.max_users] if self.max_users else active
        targets = list(self.subscribers)
        return targets[:self.max_users] if self.max_users else targets

    def verify_bot_token(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Tests bot token against Telegram getMe API."""
        t = (token or self.token or "").strip()
        if not t:
            return {"ok": False, "valid": False, "error": "No token provided"}
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(f"https://api.telegram.org/bot{t}/getMe")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok"):
                        bot = data["result"]
                        return {
                            "ok": True,
                            "valid": True,
                            "id": bot.get("id"),
                            "username": bot.get("username", ""),
                            "first_name": bot.get("first_name", ""),
                            "can_join_groups": bot.get("can_join_groups", True)
                        }
                return {"ok": False, "valid": False, "error": f"Telegram API error ({res.status_code}): {res.text}"}
        except Exception as e:
            return {"ok": False, "valid": False, "error": str(e)}

    def is_admin(self, chat_id: str) -> bool:
        """Fail-closed admin verification: if admin_chat_ids is empty, refuses all."""
        if not self.admin_chat_ids:
            return False
        return str(chat_id).strip() in self.admin_chat_ids

    def start(self):
        """Starts background long-polling for remote user commands."""
        if not self.token:
            logger.warning("[TELEGRAM] No TELEGRAM_BOT_TOKEN configured. Remote bot disabled.")
            return

        if self.running:
            return
        self.running = True
        self._http = httpx.AsyncClient(timeout=15.0)
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"[TELEGRAM] Bot client started with {len(self.subscribers)} subscribed chats.")

    def stop(self):
        self.running = False
        if self._task:
            try:
                self._task.cancel()
            except Exception:
                pass
        if self._http:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._http.aclose())
            except RuntimeError:
                try:
                    asyncio.run(self._http.aclose())
                except Exception:
                    pass
            except Exception:
                pass
            self._http = None

    async def _poll_loop(self):
        """Background long-polling loop for incoming commands."""
        while self.running:
            try:
                resp = await self._http.get(
                    f"{self.api_base}/getUpdates",
                    params={"offset": self._last_update_id + 1, "timeout": 5}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("result", []):
                        self._last_update_id = max(self._last_update_id, item["update_id"])
                        await self._process_update(item)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[TELEGRAM] Polling tick exception: {e}")
                await asyncio.sleep(2)
            await asyncio.sleep(0.5)

    async def _process_update(self, item: Dict):
        """Routes message text or inline keyboard callbacks."""
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
            # Silently acknowledge callback query
            try:
                await self._http.post(
                    f"{self.api_base}/answerCallbackQuery",
                    json={"callback_query_id": cb.get("id")}
                )
            except Exception as e:
                logger.debug(f"[TELEGRAM] Callback query answer failed: {e}")

        if not chat_id:
            return

        cmd_lower = text.lower().strip()
        if cmd_lower == "/subscribe":
            if self.max_users and len(self.subscribers) >= self.max_users and chat_id not in self.subscribers:
                asyncio.create_task(self.send_message(
                    chat_id,
                    f"⚠️ <b>TradePulse Personal Edition</b>\nSubscription limit reached (Maximum {self.max_users} authorized users).\nContact your administrator."
                ))
                logger.warning(f"[TELEGRAM] Subscription rejected for {chat_id}: Personal limit of {self.max_users} users reached.")
                return

            self.subscribers.add(chat_id)
            slot_info = f" ({len(self.subscribers)}/{self.max_users} slots used)" if self.max_users else ""
            asyncio.create_task(self.send_message(chat_id, f"✅ <b>Subscribed to real-time TradePulse Personal signals!</b>{slot_info}"))
            logger.info(f"[TELEGRAM] Chat {chat_id} subscribed to signals. Total: {len(self.subscribers)}")
            return
        elif cmd_lower == "/unsubscribe":
            self.subscribers.discard(chat_id)
            asyncio.create_task(self.send_message(chat_id, "⏸ <b>Unsubscribed from TradePulse signals.</b>"))
            logger.info(f"[TELEGRAM] Chat {chat_id} unsubscribed. Total: {len(self.subscribers)}")
            return

        # Restrict command execution to authorized personal users if max_users is enabled
        if self.max_users:
            is_authorized = (
                chat_id in self.subscribers or
                self.is_admin(chat_id) or
                (self.manager and chat_id in self.manager.get_active_channel_ids())
            )
            if not is_authorized and len(self.subscribers) >= self.max_users:
                asyncio.create_task(self.send_message(
                    chat_id,
                    f"⚠️ <b>TradePulse Personal Edition</b>\nAccess is restricted to a maximum of {self.max_users} authorized personal users.\nYour ID: <code>{chat_id}</code> is not authorized."
                ))
                logger.warning(f"[TELEGRAM] Unauthorized command from {chat_id} rejected (5-user personal cap active).")
                return

        if self.on_command:
            try:
                self.on_command(chat_id, text, {"user_name": user_name})
            except Exception as e:
                logger.error(f"[TELEGRAM] Command handler error: {e}", exc_info=True)

    def _ensure_http(self) -> httpx.AsyncClient:
        """Lazily instantiates the async HTTP client if closed or uninitialized."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def send_message(
        self,
        chat_id: str,
        text: str,
        keyboard: Optional[List[List[Dict[str, str]]]] = None
    ) -> bool:
        """Sends an HTML formatted message."""
        if not self.token:
            return False
        client = self._ensure_http()

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}

        try:
            r = await client.post(f"{self.api_base}/sendMessage", json=payload)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"[TELEGRAM] Send message error to {chat_id}: {e}")
            return False

    async def send_photo(
        self,
        chat_id: str,
        photo_bytes: bytes,
        caption: str = "",
        keyboard: Optional[List[List[Dict[str, str]]]] = None
    ) -> bool:
        """Sends a chart screenshot photo with an HTML caption."""
        if not self.token:
            return False
        client = self._ensure_http()

        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }
        if keyboard:
            data["reply_markup"] = json.dumps({"inline_keyboard": keyboard})

        files = {"photo": ("chart.png", BytesIO(photo_bytes), "image/png")}

        try:
            r = await client.post(
                f"{self.api_base}/sendPhoto",
                data=data,
                files=files,
                timeout=20.0
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"[TELEGRAM] Send photo error to {chat_id}: {e}")
            return False

    async def broadcast_signal(self, signal: Signal, chart_bytes: Optional[bytes] = None) -> int:
        """Broadcasts VIP signal card to all registered chats/channels."""
        targets = self.get_target_chats()
        if not targets or not self.token:
            return 0

        # Check manager filters
        if self.manager:
            if not self.manager.send_signals:
                logger.debug("[TELEGRAM] Confirmed signals disabled in Telegram Manager.")
                return 0
            if signal.confidence < self.manager.min_signal_score:
                logger.info(f"[TELEGRAM] Signal score {signal.confidence}% below threshold {self.manager.min_signal_score}%.")
                return 0
            if signal.live_payout is not None and signal.live_payout < self.manager.min_payout_pct:
                logger.info(f"[TELEGRAM] Signal payout {signal.live_payout}% below threshold {self.manager.min_payout_pct}%.")
                return 0
            if not self.manager.attach_chart_photo:
                chart_bytes = None

        template = self.manager.templates.get("signal") if self.manager else None
        caption, keyboard = TelegramFormatter.format_vip_signal_card(signal, template=template)
        if self.manager and not self.manager.include_inline_buttons:
            keyboard = None

        sent = 0
        for cid in targets:
            ok = False
            if chart_bytes:
                ok = await self.send_photo(cid, chart_bytes, caption, keyboard)
            if not ok:
                ok = await self.send_message(cid, caption, keyboard)
            if ok:
                sent += 1

        logger.info(f"[TELEGRAM] Signal {signal.id[:8]} dispatched to {sent}/{len(targets)} channels.")
        return sent

    async def broadcast_outcome(self, signal: Signal) -> int:
        """Broadcasts trade WIN/LOSS outcome notification to all subscribers."""
        targets = self.get_target_chats()
        if not targets or not self.token:
            return 0

        if self.manager and not self.manager.send_outcomes:
            logger.debug("[TELEGRAM] Outcomes disabled in Telegram Manager.")
            return 0

        template = self.manager.templates.get("outcome") if self.manager else None
        text = TelegramFormatter.format_trade_outcome_card(signal, template=template)
        sent = 0

        for cid in targets:
            if await self.send_message(cid, text):
                sent += 1

        logger.info(f"[TELEGRAM] Outcome for {signal.id[:8]} ({signal.status}) sent to {sent}/{len(targets)} channels.")
        return sent

    async def broadcast_pre_signal(
        self,
        symbol: str,
        direction: str,
        timeframe: str,
        expiry_minutes: int,
        remaining_seconds: int,
        price: float,
        payout: Optional[float],
        strategy_name: str,
        stake: Optional[float] = None,
        martingale_step: int = 1
    ) -> int:
        """Broadcasts lightweight 15s pre-signal radar alert."""
        targets = self.get_target_chats()
        if not targets or not self.token or not getattr(settings, "PRE_ALERTS_ENABLED", True):
            return 0

        if self.manager and not self.manager.send_pre_signals:
            logger.debug("[TELEGRAM] Pre-signals disabled in Telegram Manager.")
            return 0

        template = self.manager.templates.get("pre_signal") if self.manager else None
        text = TelegramFormatter.format_pre_signal_card(
            symbol=symbol,
            direction=direction,
            timeframe=timeframe,
            expiry_minutes=expiry_minutes,
            remaining_seconds=remaining_seconds,
            price=price,
            payout=payout,
            strategy_name=strategy_name,
            template=template,
            stake=stake,
            martingale_step=martingale_step
        )
        sent = 0
        for cid in targets:
            if await self.send_message(cid, text):
                sent += 1
        return sent

    async def broadcast_circuit_breaker(self, metrics: Dict[str, Any]) -> int:
        """Broadcasts Take Profit or Stop Loss circuit breaker notification."""
        targets = self.get_target_chats()
        if not targets or not self.token:
            return 0

        if self.manager and not self.manager.send_circuit_breaker:
            return 0

        template = self.manager.templates.get("circuit_breaker") if self.manager else None
        text = TelegramFormatter.format_circuit_breaker_card(metrics, template=template)
        sent = 0
        for cid in targets:
            if await self.send_message(cid, text):
                sent += 1
        return sent

    async def broadcast_custom_message(self, text: str, target_chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Broadcasts custom announcement text to specified chat or all active channels."""
        if not self.token:
            return {"success": False, "error": "Telegram Bot Token not configured"}

        targets = [target_chat_id.strip()] if target_chat_id and target_chat_id.strip() else self.get_target_chats()
        if not targets:
            return {"success": False, "error": "No destination channels configured"}

        sent = 0
        failed = 0
        for cid in targets:
            if await self.send_message(cid, text):
                sent += 1
            else:
                failed += 1

        return {
            "success": sent > 0,
            "sent": sent,
            "sent_count": sent,
            "failed": failed,
            "total": len(targets)
        }

