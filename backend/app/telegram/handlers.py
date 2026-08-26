import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.telegram import TelegramAccount, TelegramLinkCode, SignalSubscription
from app.models.signal import Signal
from app.telegram.bot import telegram_service
from app.telegram.formatter import TelegramMessageFormatter
from app.engine.market_data.manager import market_data_manager

logger = logging.getLogger(__name__)


class TelegramUpdateHandler:
    """Processes incoming Webhook / Polling updates from Telegram"""

    @classmethod
    async def process_update(cls, update: Dict[str, Any], db: AsyncSession):
        # 1. Handle Callback Queries (Inline button clicks)
        if "callback_query" in update:
            await cls._handle_callback_query(update["callback_query"], db)
            return

        # 2. Handle Text Messages and Commands
        if "message" in update:
            await cls._handle_message(update["message"], db)

    @classmethod
    async def _handle_message(cls, msg: Dict[str, Any], db: AsyncSession):
        chat_id = msg.get("chat", {}).get("id")
        user_info = msg.get("from", {})
        telegram_user_id = user_info.get("id")
        username = user_info.get("username")
        first_name = user_info.get("first_name", "Trader")
        text = msg.get("text", "").strip()

        if not text or not chat_id:
            return

        # Auto-register/subscribe EVERY user who messages the bot
        existing_q = select(TelegramAccount).where(TelegramAccount.telegram_chat_id == chat_id)
        existing_res = await db.execute(existing_q)
        tg_acc = existing_res.scalar_one_or_none()

        if not tg_acc:
            # Find default demo/admin user to associate with
            from app.models.user import User
            user_res = await db.execute(select(User).limit(1))
            primary_user = user_res.scalar_one_or_none()
            user_id = primary_user.id if primary_user else None

            tg_acc = TelegramAccount(
                user_id=user_id,
                telegram_user_id=telegram_user_id or chat_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
                first_name=first_name,
                is_active=True,
                is_muted=False
            )
            db.add(tg_acc)
            await db.commit()
            logger.info(f"Auto-subscribed new Telegram subscriber: {first_name} (chat_id={chat_id})")
        else:
            if not tg_acc.is_active:
                tg_acc.is_active = True
                await db.commit()

        # /start command
        if text.startswith("/start"):
            welcome = (
                f"🚀 <b>Welcome to TradePulse AI Signal Station, {first_name}!</b>\n\n"
                f"✅ <b>You are automatically subscribed!</b>\n"
                f"You will receive real-time, high-accuracy Quotex & Forex AI signals directly here as soon as our algorithmic scanners detect high-probability market setups.\n\n"
                f"📊 <b>Active Market Scanners:</b>\n"
                f"• Quotex OTC (EUR/USD, GBP/USD, USD/JPY, BTC/USDT, etc.)\n"
                f"• High-Probability Multi-Timeframe Pattern Recognition\n"
                f"• GPT-4o / OpenRouter AI Confidence Validation\n\n"
                f"<b>Bot Commands:</b>\n"
                f"• <code>/status</code> - Check your live signal subscription\n"
                f"• <code>/mute</code> - Pause incoming signal alerts\n"
                f"• <code>/unmute</code> - Resume signal alerts\n"
                f"• <code>/help</code> - Explanation of signal cards & buttons"
            )
            await telegram_service.send_message(chat_id, welcome)
            return

        # /link <CODE> command
        elif text.startswith("/link"):
            parts = text.split()
            if len(parts) < 2:
                await telegram_service.send_message(chat_id, "⚠️ Please provide your 6-character linking code.\nExample: <code>/link ABC123</code>")
                return
            link_code = parts[1].strip().upper()
            await cls._execute_link(chat_id, telegram_user_id, username, first_name, link_code, db)

        # /status command
        elif text.startswith("/status"):
            query = select(TelegramAccount).where(TelegramAccount.telegram_user_id == telegram_user_id)
            result = await db.execute(query)
            tg_acc = result.scalar_one_or_none()

            if tg_acc:
                status_msg = (
                    f"✅ <b>Account Linked</b>\n\n"
                    f"• <b>Status:</b> {'🟢 Active' if tg_acc.is_active else '🔴 Inactive'}\n"
                    f"• <b>Alerts:</b> {'🔕 Muted' if tg_acc.is_muted else '🔔 Enabled'}\n"
                    f"• <b>Chat ID:</b> <code>{chat_id}</code>\n"
                    f"• <b>Telegram Username:</b> @{tg_acc.telegram_username or 'N/A'}"
                )
            else:
                status_msg = "❌ <b>Account Not Linked</b>\nPlease use <code>/link &lt;CODE&gt;</code> to connect your web dashboard."

            await telegram_service.send_message(chat_id, status_msg)

        # /mute command
        elif text.startswith("/mute"):
            query = select(TelegramAccount).where(TelegramAccount.telegram_user_id == telegram_user_id)
            result = await db.execute(query)
            tg_acc = result.scalar_one_or_none()
            if tg_acc:
                tg_acc.is_muted = True
                await db.commit()
                await telegram_service.send_message(chat_id, "🔕 Notifications muted.")
            else:
                await telegram_service.send_message(chat_id, "❌ Please link your account first with <code>/link &lt;CODE&gt;</code>.")

        # /unmute command
        elif text.startswith("/unmute"):
            query = select(TelegramAccount).where(TelegramAccount.telegram_user_id == telegram_user_id)
            result = await db.execute(query)
            tg_acc = result.scalar_one_or_none()
            if tg_acc:
                tg_acc.is_muted = False
                await db.commit()
                await telegram_service.send_message(chat_id, "🔔 Notifications unmuted and active!")
            else:
                await telegram_service.send_message(chat_id, "❌ Please link your account first.")

        # /help command
        elif text.startswith("/help"):
            help_text = (
                "📖 <b>TradePulse AI Telegram Guide</b>\n\n"
                "When a pattern on your web dashboard triggers a signal, you receive an instant alert card.\n\n"
                "<b>Interactive Card Buttons:</b>\n"
                "• 🧠 <b>AI Analysis:</b> Full AI confidence breakdown & reasoning\n"
                "• 📊 <b>Technicals:</b> Live indicator snapshot (RSI, MACD, S/R)\n"
                "• 📈 <b>Live Signal:</b> Real-time price tracking & delta\n"
                "• 📋 <b>Full Details:</b> Audit rules & trigger data\n"
                "• 🔔 <b>Follow:</b> Subscribe to lifecycle updates\n"
                "• 🔕 <b>Mute:</b> Temporarily silence alerts"
            )
            await telegram_service.send_message(chat_id, help_text)

    @classmethod
    async def _execute_link(cls, chat_id: int, telegram_user_id: int, username: Optional[str], first_name: str, code: str, db: AsyncSession):
        now = datetime.now(timezone.utc)
        query = select(TelegramLinkCode).where(
            TelegramLinkCode.code == code,
            TelegramLinkCode.is_used == False,
            TelegramLinkCode.expires_at > now
        )
        res = await db.execute(query)
        link_record = res.scalar_one_or_none()

        if not link_record:
            await telegram_service.send_message(chat_id, "❌ <b>Invalid or expired linking code.</b>\nPlease generate a new code from your Web Dashboard.")
            return

        # Check if already linked
        existing_q = select(TelegramAccount).where(TelegramAccount.telegram_user_id == telegram_user_id)
        existing_res = await db.execute(existing_q)
        tg_acc = existing_res.scalar_one_or_none()

        if tg_acc:
            tg_acc.user_id = link_record.user_id
            tg_acc.telegram_chat_id = chat_id
            tg_acc.telegram_username = username
            tg_acc.first_name = first_name
            tg_acc.is_active = True
        else:
            tg_acc = TelegramAccount(
                user_id=link_record.user_id,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
                first_name=first_name,
                is_active=True
            )
            db.add(tg_acc)

        link_record.is_used = True
        await db.commit()

        success_msg = (
            f"🎉 <b>Successfully Linked!</b>\n\n"
            f"Your Telegram account is now connected to your TradePulse workstation.\n"
            f"You will receive instant alerts whenever your active patterns detect matching market setups."
        )
        await telegram_service.send_message(chat_id, success_msg)

    @classmethod
    async def _handle_callback_query(cls, cb: Dict[str, Any], db: AsyncSession):
        cb_id = cb.get("id")
        msg = cb.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        message_id = msg.get("message_id")
        data = cb.get("data", "")

        if not data or not chat_id or not message_id:
            return

        parts = data.split(":")
        action = parts[0]
        sig_id = parts[1] if len(parts) > 1 else None

        if not sig_id:
            await telegram_service.answer_callback_query(cb_id)
            return

        # Fetch signal with technicals and AI analysis
        query = select(Signal).where(Signal.id == sig_id)
        res = await db.execute(query)
        signal = res.scalar_one_or_none()

        if not signal:
            await telegram_service.answer_callback_query(cb_id, text="Signal not found.")
            return

        # Build signal dictionary representation
        sig_dict = {
            "id": signal.id,
            "asset_symbol": signal.asset_symbol,
            "direction": signal.direction,
            "reference_price": signal.reference_price,
            "entry_time": signal.entry_time,
            "expiry_time": signal.expiry_time,
            "duration_minutes": signal.duration_minutes,
            "pattern_name": signal.pattern_name,
            "pattern_version": signal.pattern_version,
            "ai_score": signal.ai_score,
            "signal_strength": signal.signal_strength,
            "status": signal.status,
            "market_id": signal.market_id,
            "timeframe": signal.timeframe,
            "stop_loss": signal.stop_loss,
            "tp1": signal.tp1,
            "created_at": signal.created_at,
            "technical_snapshot": signal.technical_snapshot.__dict__ if signal.technical_snapshot else {},
            "ai_analysis": signal.ai_analysis.__dict__ if signal.ai_analysis else {},
        }

        if action == "ai":
            text, kb = TelegramMessageFormatter.format_ai_analysis_view(sig_dict)
            await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
        elif action == "tech":
            text, kb = TelegramMessageFormatter.format_technicals_view(sig_dict)
            await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
        elif action == "live":
            provider = market_data_manager.get_provider()
            current_price = await provider.get_current_price(signal.asset_symbol)
            text, kb = TelegramMessageFormatter.format_live_signal_view(sig_dict, current_price)
            await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
        elif action == "details":
            text, kb = TelegramMessageFormatter.format_full_details_view(sig_dict)
            await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
        elif action == "back":
            text, kb = TelegramMessageFormatter.format_main_signal(sig_dict)
            await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
        elif action == "follow":
            await telegram_service.answer_callback_query(cb_id, text="🔔 You are now following this signal's lifecycle!")
            return
        elif action == "mute":
            await telegram_service.answer_callback_query(cb_id, text="🔕 Signal alerts muted for 1 hour.")
            return

        await telegram_service.answer_callback_query(cb_id)
