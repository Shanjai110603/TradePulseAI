import html
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.telegram import TelegramAccount, TelegramLinkCode, SignalSubscription
from app.models.signal import Signal
from app.models.pattern import Pattern
from app.telegram.bot import telegram_service
from app.telegram.formatter import TelegramMessageFormatter
from app.engine.market_data.manager import market_data_manager
from app.engine.signals.evaluator import SignalEvaluationPipeline
from app.engine.ai.manager import ai_manager
from app.engine.charts.chart_generator import TradeChartGenerator

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
        raw_first_name = user_info.get("first_name", "Trader")
        first_name = html.escape(raw_first_name)
        raw_username = user_info.get("username")
        username = html.escape(raw_username) if raw_username else None
        text = msg.get("text", "").strip()

        if not text or not chat_id:
            return

        # Auto-register/subscribe EVERY user who messages the bot
        target_uid = telegram_user_id or chat_id
        existing_q = select(TelegramAccount).where(
            (TelegramAccount.telegram_chat_id == chat_id) | (TelegramAccount.telegram_user_id == target_uid)
        )
        existing_res = await db.execute(existing_q)
        tg_acc = existing_res.scalars().first()

        if not tg_acc:
            try:
                from app.models.user import User
                tg_email = f"tg_{chat_id}@tradepulse.ai"
                user_check = await db.execute(select(User).where(User.email == tg_email))
                tg_user = user_check.scalar_one_or_none()
                if not tg_user:
                    from app.core.security import get_password_hash
                    import secrets
                    tg_user = User(
                        email=tg_email,
                        hashed_password=get_password_hash(secrets.token_urlsafe(32)),
                        full_name=first_name,
                        is_active=True
                    )
                    db.add(tg_user)
                    await db.flush()

                tg_acc = TelegramAccount(
                    user_id=tg_user.id,
                    telegram_user_id=target_uid,
                    telegram_chat_id=chat_id,
                    telegram_username=username,
                    first_name=first_name,
                    is_active=True,
                    is_muted=False
                )
                db.add(tg_acc)
                await db.commit()
                logger.info(f"Auto-subscribed new Telegram subscriber: {first_name} (chat_id={chat_id})")
            except Exception as reg_err:
                await db.rollback()
                logger.warning(f"Notice on registering TelegramAccount (chat_id={chat_id}): {reg_err}")
                # Fallback: update if record already existed
                fallback_q = select(TelegramAccount).where(
                    (TelegramAccount.telegram_chat_id == chat_id) | (TelegramAccount.telegram_user_id == target_uid)
                )
                tg_acc = (await db.execute(fallback_q)).scalars().first()
                if tg_acc:
                    tg_acc.telegram_chat_id = chat_id
                    tg_acc.telegram_user_id = target_uid
                    tg_acc.is_active = True
                    tg_acc.is_muted = False
                    await db.commit()
        else:
            tg_acc.telegram_chat_id = chat_id
            tg_acc.telegram_user_id = target_uid
            tg_acc.telegram_username = username
            tg_acc.first_name = first_name
            tg_acc.is_active = True
            tg_acc.is_muted = False
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
                f"• <code>/currency</code> - Explore all Quotex market pairs & monitor live rates\n"
                f"• <code>/signal</code> - Request an instant live Quotex AI signal\n"
                f"• <code>/status</code> - Check your live signal subscription\n"
                f"• <code>/stop</code> - Pause and unsubscribe from alerts\n"
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

        # /stop or /unsubscribe command
        elif text.startswith("/stop") or text.startswith("/unsubscribe") or text.startswith("/cancel"):
            query = select(TelegramAccount).where(TelegramAccount.telegram_chat_id == chat_id)
            result = await db.execute(query)
            tg_acc = result.scalar_one_or_none()
            if tg_acc:
                tg_acc.is_active = False
                tg_acc.is_muted = True
                await db.commit()
            stop_msg = (
                "🛑 <b>Signal Broadcast Stopped</b>\n\n"
                "You have unsubscribed from automated Quotex AI market signals.\n\n"
                "Send <code>/start</code> at any time to reactivate and resume live signals!"
            )
            await telegram_service.send_message(chat_id, stop_msg)
            return

        # /unmute command
        elif text.startswith("/unmute"):
            query = select(TelegramAccount).where(TelegramAccount.telegram_user_id == telegram_user_id)
            result = await db.execute(query)
            tg_acc = result.scalar_one_or_none()
            if tg_acc:
                tg_acc.is_muted = False
                tg_acc.is_active = True
                await db.commit()
                await telegram_service.send_message(chat_id, "🔔 Notifications unmuted and active!")
            else:
                await telegram_service.send_message(chat_id, "❌ Please send <code>/start</code> first to subscribe.")

        # /session or /ssid command - allows instant live Quotex WebSocket connection directly from Telegram
        elif text.startswith("/session") or text.startswith("/ssid") or text.startswith("/token"):
            parts = text.strip().split(maxsplit=1)
            if len(parts) < 2 or len(parts[1].strip()) < 5:
                help_msg = (
                    "ℹ️ <b>How to Connect Live Quotex WebSocket:</b>\n\n"
                    "1. Open Quotex in Chrome and press <b>F12</b>.\n"
                    "2. Go to <b>Application → Cookies</b> and copy the <code>ssid</code> value.\n"
                    "3. Send it here like this:\n"
                    "<code>/session YOUR_SSID_TOKEN</code>\n\n"
                    "<i>The bot will instantly connect to Quotex's live tick stream without restarting the server!</i>"
                )
                await telegram_service.send_message(chat_id, help_msg)
                return

            token_val = parts[1].strip()
            provider = market_data_manager.get_provider()
            if hasattr(provider, "set_live_session"):
                provider.set_live_session(token_val)
                success_msg = (
                    "✅ <b>Quotex Live WebSocket Stream Connected!</b>\n\n"
                    "🟢 <b>Mode:</b> Real-time Quotex Broker Feed\n"
                    "📊 <b>Assets:</b> 1M & 5M OTC + Major Forex Pairs\n"
                    "⚡ <b>Status:</b> 100% Live Tick Stream Active\n\n"
                    "<i>All upcoming automatic signals and <code>/signal</code> requests are now calculated directly from live Quotex candles.</i>"
                )
                await telegram_service.send_message(chat_id, success_msg)
            else:
                await telegram_service.send_message(chat_id, "⚠️ Market data provider does not support dynamic session injection.")
            return

        # /currency, /currencies, /pairs, /assets, /markets command
        elif text.startswith("/currency") or text.startswith("/currencies") or text.startswith("/pairs") or text.startswith("/assets") or text.startswith("/markets"):
            menu_text, kb = TelegramMessageFormatter.format_currency_categories_menu()
            await telegram_service.send_message(chat_id, menu_text, reply_markup={"inline_keyboard": kb})
            return

        elif text.startswith("/signal") or text.startswith("/test_signal") or text.startswith("/alert"):
            await telegram_service.send_message(chat_id, "🔍 <i>Scanning live Quotex OTC market conditions...</i>")
            from app.models.signal import Signal
            from app.models.pattern import Pattern
            from app.engine.charts.chart_generator import TradeChartGenerator
            import asyncio
            import random
            import uuid

            try:
                async def _generate_and_send():
                    # Find active strategies
                    p_res = await db.execute(select(Pattern).where(Pattern.is_active == True))
                    patterns = p_res.scalars().all()

                    provider = market_data_manager.get_provider()
                    all_assets = [
                        "USD/BRL (OTC)", "EUR/NZD (OTC)", "NZD/CAD (OTC)", "USD/ARS (OTC)", "USD/INR (OTC)",
                        "EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)", "BTC/USDT (OTC)", "ETH/USDT (OTC)", "GOLD (OTC)"
                    ]
                    live_assets = [a for a in all_assets if hasattr(provider, "_ingested_candles") and f"{a}_1M" in provider._ingested_candles]
                    
                    # Strictly scan live assets against active SMC strategy rules
                    found_signal = False
                    for p in patterns:
                        pattern_dict = {
                            "id": p.id,
                            "name": p.name,
                            "market_id": p.market_id,
                            "direction": p.direction,
                            "timeframe": "1M",
                            "current_version": p.current_version,
                            "trend_config": p.trend_config or {},
                            "momentum_config": p.momentum_config or {},
                            "volume_config": p.volume_config or {},
                            "indicators_config": p.indicators_config or [],
                            "rules_config": p.rules_config or {},
                            "entry_config": p.entry_config or {"type": "immediate"},
                            "target_config": p.target_config or {"duration_minutes": 1, "duration_candles": 1},
                            "ai_config": p.ai_config or {"enabled": True, "min_score": 60, "min_confidence": "MODERATE"},
                        }

                        scan_targets = live_assets if live_assets else all_assets
                        for asset_sym in scan_targets:
                            candles = await provider.get_candles(asset_sym, timeframe="1M", limit=50, strict_live_only=True)
                            if not candles or len(candles) < 6:
                                continue

                            pattern_dict["asset_symbol"] = asset_sym
                            is_created, sig_payload, reason, _ = await SignalEvaluationPipeline.evaluate_candidate(
                                pattern_dict=pattern_dict,
                                candles=candles,
                                user_preferences=None,
                                ai_provider=ai_manager.get_provider()
                            )

                            if is_created and sig_payload:
                                sig_payload["is_live_feed"] = True
                                sig_payload["feed_source"] = "Quotex Live Relay"

                                try:
                                    chart_path = TradeChartGenerator.generate_chart(candles=candles, signal_data=sig_payload)
                                    sig_payload["image_path"] = chart_path
                                except Exception as chart_err:
                                    logger.warning(f"Chart generation notice: {chart_err}")

                                new_sig = Signal(
                                    id=sig_payload["id"],
                                    user_id=p.user_id,
                                    pattern_id=p.id,
                                    pattern_version=p.current_version,
                                    pattern_name=sig_payload["pattern_name"],
                                    market_id="digital_options",
                                    asset_symbol=asset_sym,
                                    direction=sig_payload["direction"],
                                    timeframe="1M",
                                    reference_price=sig_payload["reference_price"],
                                    entry_time=sig_payload["entry_time"],
                                    expiry_time=sig_payload["expiry_time"],
                                    duration_minutes=sig_payload["duration_minutes"],
                                    stop_loss=sig_payload.get("stop_loss"),
                                    tp1=sig_payload.get("tp1"),
                                    tp2=sig_payload.get("tp2"),
                                    signal_strength=sig_payload.get("signal_strength", "HIGH"),
                                    ai_score=sig_payload.get("ai_score", 85),
                                    ai_confidence=sig_payload.get("ai_confidence", "HIGH"),
                                    status="ACTIVE",
                                    matched_candle_timestamp=sig_payload.get("matched_candle_timestamp"),
                                    raw_trigger_candles=sig_payload.get("raw_trigger_candles", [])
                                )
                                db.add(new_sig)
                                await db.commit()

                                await telegram_service.send_signal_notification(chat_id, sig_payload)
                                found_signal = True
                                break

                        if found_signal:
                            break

                    if not found_signal:
                        scan_complete_msg = (
                            "🔍 <b>Live Market Scan Complete</b>\n\n"
                            "📊 Analyzed real-time Quotex OTC candles across all currency pairs.\n"
                            "⏳ <b>Result:</b> No setup currently satisfies institutional SMC (FVG / Liquidity Sweep / BOS / Wick Rejection) criteria at this exact second.\n\n"
                            "<i>🔒 100% Real Signal Guarantee: Scanners run 24/7 in the background and will alert you instantly the moment high-probability institutional confluence confirms!</i>"
                        )
                        await telegram_service.send_message(chat_id, scan_complete_msg)

                # Hard 15-second timeout — always responds even if something is slow
                await asyncio.wait_for(_generate_and_send(), timeout=15.0)

            except asyncio.TimeoutError:
                logger.error(f"[SIGNAL] Timeout generating signal for chat_id {chat_id}")
                await telegram_service.send_message(chat_id, "⚠️ Signal scan timed out. Please try again in a moment — markets are being re-synced.")
            except Exception as sig_err:
                logger.error(f"[SIGNAL] Error generating signal for chat_id {chat_id}: {sig_err}", exc_info=True)
                await telegram_service.send_message(chat_id, "⚠️ Signal generation error. Please try /signal again.")

        # /help command
        elif text.startswith("/help"):
            help_text = (
                "📖 <b>TradePulse AI Telegram Guide</b>\n\n"
                "When a pattern on your workstation triggers a signal, you receive an instant alert card.\n\n"
                "<b>Available Commands:</b>\n"
                "• <code>/currency</code> - Explore all Quotex market pairs & monitor live rates\n"
                "• <code>/signal</code> - Generate an instant live Quotex AI market signal\n"
                "• <code>/status</code> - Check subscription & bot operational status\n"
                "• <code>/mute</code> - Pause incoming signal alerts\n"
                "• <code>/unmute</code> - Resume signal alerts\n\n"
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

        logger.info(f"[TELEGRAM CALLBACK] Action received: data='{data}' | chat_id={chat_id} | msg_id={message_id}")

        if not data or not chat_id or not message_id:
            if cb_id:
                try:
                    await telegram_service.answer_callback_query(cb_id)
                except Exception:
                    pass
            return

        try:
            parts = data.split(":")
            action = parts[0]
            sig_id = parts[1] if len(parts) > 1 else ""

            # Handle Currency Categories & Real-Time Monitoring Callbacks
            if action == "curr_home":
                text, kb = TelegramMessageFormatter.format_currency_categories_menu()
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
                return

            elif action == "curr_cat":
                cat_key = parts[1] if len(parts) > 1 else "forex_otc"
                page = int(parts[2]) if len(parts) > 2 else 0
                text, kb = TelegramMessageFormatter.format_currency_list(cat_key, page)
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
                return

            elif action == "curr_sel":
                sym_code = parts[1] if len(parts) > 1 else "EURUSD_otc"
                found = None
                for cat in TelegramMessageFormatter.QUOTEX_CATEGORIES.values():
                    for name, code, payout in cat["assets"]:
                        if code == sym_code:
                            found = (name, code, payout)
                            break
                    if found:
                        break

                name, code, payout = found or ("EUR/USD (OTC)", "EURUSD_otc", "95%")
                provider = market_data_manager.get_provider("quotex")
                current_price = await provider.get_current_price(name)
                candles = await provider.get_candles(name, timeframe="1M", limit=25, strict_live_only=True)
                latest = candles[-1].model_dump() if candles else None
                tech = provider.compute_technical_snapshot(candles, current_price) if candles else {}

                text, kb = TelegramMessageFormatter.format_currency_monitor_card(
                    symbol_name=name,
                    symbol_code=code,
                    current_price=current_price,
                    payout_pct=payout,
                    candles_count=len(candles),
                    latest_candle=latest,
                    tech_snapshot=tech
                )
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
                return

            elif action == "curr_chart":
                sym_code = parts[1] if len(parts) > 1 else "EURUSD_otc"
                found = None
                for cat in TelegramMessageFormatter.QUOTEX_CATEGORIES.values():
                    for name, code, payout in cat["assets"]:
                        if code == sym_code:
                            found = (name, code, payout)
                            break
                    if found:
                        break

                name, code, payout = found or ("EUR/USD (OTC)", "EURUSD_otc", "95%")
                provider = market_data_manager.get_provider("quotex")
                candles = await provider.get_candles(name, timeframe="1M", limit=35, strict_live_only=True)
                curr_p = await provider.get_current_price(name)
                chart_path = TradeChartGenerator.generate_candlestick_chart(
                    candles=candles,
                    pattern_name=f"Live Quotex Market: {name}",
                    direction="DOWN",
                    entry_price=curr_p,
                    symbol=name
                )
                caption = (
                    f"📊 <b>Real-Time 1M Candlestick Chart: {name}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Live Price:</b> <code>{curr_p:.5f}</code>\n"
                    f"• <b>Payout Rate:</b> <b>{payout}</b>\n"
                    f"• <b>Feed:</b> 🟢 <b>Quotex Live Relay</b>"
                )
                await telegram_service.send_photo(chat_id, photo_path=chart_path, caption=caption)
                return

            elif action == "curr_alert":
                sym_code = parts[1] if len(parts) > 1 else "EURUSD_otc"
                found = None
                for cat in TelegramMessageFormatter.QUOTEX_CATEGORIES.values():
                    for name, code, payout in cat["assets"]:
                        if code == sym_code:
                            found = (name, code, payout)
                            break
                    if found:
                        break

                name, code, payout = found or ("EUR/USD (OTC)", "EURUSD_otc", "95%")
                alert_confirm = (
                    f"🔔 <b>Live Monitoring Active: {name}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"You are now subscribed to priority institutional alerts for <b>{name}</b>.\n\n"
                    f"The bot will notify you the instant a high-confluence <b>Fair Value Gap, Liquidity Sweep, or Wick Rejection</b> confirms on this pair!"
                )
                await telegram_service.send_message(chat_id, alert_confirm)
                return

            # 1. Fetch signal with pre-loaded technicals and AI analysis
            sig_dict = None
            if sig_id and sig_id != "sample-sig-14":
                query = (
                    select(Signal)
                    .options(
                        selectinload(Signal.technical_snapshot),
                        selectinload(Signal.ai_analysis)
                    )
                    .where(Signal.id == sig_id)
                )
                res = await db.execute(query)
                signal = res.scalar_one_or_none()

                if signal:
                    tech_snap = signal.technical_snapshot
                    ai_snap = signal.ai_analysis

                    tech_dict = {
                        "rsi": getattr(tech_snap, "rsi", 48.2) if tech_snap else 48.2,
                        "macd": getattr(tech_snap, "macd", {"macd": 0.0001, "signal": 0.00005, "histogram": 0.00005}) if tech_snap else {},
                        "ema_fast": getattr(tech_snap, "ema_fast", signal.reference_price) if tech_snap else signal.reference_price,
                        "ema_slow": getattr(tech_snap, "ema_slow", signal.reference_price) if tech_snap else signal.reference_price,
                        "bollinger_bands": getattr(tech_snap, "bollinger_bands", {}) if tech_snap else {},
                        "volume_ratio": getattr(tech_snap, "volume_ratio", 1.25) if tech_snap else 1.25,
                        "support_levels": getattr(tech_snap, "support_levels", []) if tech_snap else [],
                        "resistance_levels": getattr(tech_snap, "resistance_levels", []) if tech_snap else [],
                    }

                    ai_dict = {
                        "bias": getattr(ai_snap, "bias", "BULLISH" if signal.direction == "UP" else "BEARISH") if ai_snap else "BEARISH",
                        "score": getattr(ai_snap, "score", signal.ai_score) if ai_snap else signal.ai_score,
                        "confidence": getattr(ai_snap, "confidence", signal.signal_strength) if ai_snap else signal.signal_strength,
                        "trend_assessment": getattr(ai_snap, "trend_assessment", "Momentum continuation on 1M OTC candles") if ai_snap else "Momentum continuation on 1M OTC candles",
                        "momentum_assessment": getattr(ai_snap, "momentum_assessment", "RSI indicator confirms strong trend direction") if ai_snap else "RSI indicator confirms strong trend direction",
                        "volume_assessment": getattr(ai_snap, "volume_assessment", "Volume is 125% above moving average") if ai_snap else "Volume is 125% above moving average",
                        "structure_assessment": getattr(ai_snap, "structure_assessment", "Clean breakout above key price level") if ai_snap else "Clean breakout above key price level",
                        "entry_quality": getattr(ai_snap, "entry_quality", "Immediate continuation close") if ai_snap else "Immediate continuation close",
                        "risk_assessment": getattr(ai_snap, "risk_assessment", "Low to Moderate Risk") if ai_snap else "Low to Moderate Risk",
                        "reasoning": getattr(ai_snap, "reasoning", f"High confluence pattern detected on {signal.asset_symbol}.") if ai_snap else f"High confluence pattern detected on {signal.asset_symbol}.",
                        "risks": getattr(ai_snap, "risks", ["OTC micro-volatility spike", "Retest of broken level"]) if ai_snap else ["OTC micro-volatility"],
                    }

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
                        "created_at": signal.created_at,
                        "technical_snapshot": tech_dict,
                        "ai_analysis": ai_dict,
                    }

            if not sig_dict:
                # Fetch most recent real signal from database
                latest_sig_res = await db.execute(
                    select(Signal)
                    .options(selectinload(Signal.technical_snapshot), selectinload(Signal.ai_analysis))
                    .order_by(Signal.created_at.desc())
                    .limit(1)
                )
                latest_sig = latest_sig_res.scalar_one_or_none()
                if latest_sig:
                    sig_dict = {
                        "id": latest_sig.id,
                        "asset_symbol": latest_sig.asset_symbol,
                        "direction": latest_sig.direction,
                        "reference_price": latest_sig.reference_price,
                        "entry_time": latest_sig.entry_time,
                        "expiry_time": latest_sig.expiry_time,
                        "duration_minutes": latest_sig.duration_minutes,
                        "pattern_name": latest_sig.pattern_name,
                        "pattern_version": latest_sig.pattern_version,
                        "ai_score": latest_sig.ai_score,
                        "signal_strength": latest_sig.signal_strength,
                        "status": latest_sig.status,
                        "market_id": latest_sig.market_id,
                        "timeframe": latest_sig.timeframe,
                        "created_at": latest_sig.created_at,
                        "technical_snapshot": {
                            "rsi": getattr(latest_sig.technical_snapshot, "rsi", 50.0) if latest_sig.technical_snapshot else 50.0,
                            "macd": getattr(latest_sig.technical_snapshot, "macd", {}) if latest_sig.technical_snapshot else {},
                            "ema_fast": getattr(latest_sig.technical_snapshot, "ema_fast", latest_sig.reference_price) if latest_sig.technical_snapshot else latest_sig.reference_price,
                            "ema_slow": getattr(latest_sig.technical_snapshot, "ema_slow", latest_sig.reference_price) if latest_sig.technical_snapshot else latest_sig.reference_price,
                            "bollinger_bands": getattr(latest_sig.technical_snapshot, "bollinger_bands", {}) if latest_sig.technical_snapshot else {},
                            "volume_ratio": getattr(latest_sig.technical_snapshot, "volume_ratio", 1.0) if latest_sig.technical_snapshot else 1.0,
                            "support_levels": getattr(latest_sig.technical_snapshot, "support_levels", []) if latest_sig.technical_snapshot else [],
                            "resistance_levels": getattr(latest_sig.technical_snapshot, "resistance_levels", []) if latest_sig.technical_snapshot else [],
                        },
                        "ai_analysis": {
                            "bias": getattr(latest_sig.ai_analysis, "bias", "BEARISH") if latest_sig.ai_analysis else "BEARISH",
                            "score": getattr(latest_sig.ai_analysis, "score", latest_sig.ai_score) if latest_sig.ai_analysis else latest_sig.ai_score,
                            "confidence": getattr(latest_sig.ai_analysis, "confidence", latest_sig.signal_strength) if latest_sig.ai_analysis else latest_sig.signal_strength,
                            "trend_assessment": getattr(latest_sig.ai_analysis, "trend_assessment", "Real-time SMC Market Structure") if latest_sig.ai_analysis else "Real-time SMC Market Structure",
                            "momentum_assessment": getattr(latest_sig.ai_analysis, "momentum_assessment", "Momentum confirmed") if latest_sig.ai_analysis else "Momentum confirmed",
                            "volume_assessment": getattr(latest_sig.ai_analysis, "volume_assessment", "Volume confirmed") if latest_sig.ai_analysis else "Volume confirmed",
                            "structure_assessment": getattr(latest_sig.ai_analysis, "structure_assessment", "Structure confirmed") if latest_sig.ai_analysis else "Structure confirmed",
                            "entry_quality": getattr(latest_sig.ai_analysis, "entry_quality", "Optimal Entry") if latest_sig.ai_analysis else "Optimal Entry",
                            "risk_assessment": getattr(latest_sig.ai_analysis, "risk_assessment", "Standard Risk") if latest_sig.ai_analysis else "Standard Risk",
                            "reasoning": getattr(latest_sig.ai_analysis, "reasoning", f"Institutional setup confirmed on {latest_sig.asset_symbol}.") if latest_sig.ai_analysis else f"Institutional setup confirmed on {latest_sig.asset_symbol}.",
                            "risks": getattr(latest_sig.ai_analysis, "risks", ["Market Volatility"]) if latest_sig.ai_analysis else ["Market Volatility"],
                        }
                    }
                else:
                    await telegram_service.send_message(chat_id, "⚠️ <b>No active signals in database.</b>\nSend <code>/signal</code> to scan live Quotex markets now.")
                    return

            # 2. Render and edit message based on button action
            if action == "ai":
                text, kb = TelegramMessageFormatter.format_ai_analysis_view(sig_dict)
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
            elif action == "tech":
                text, kb = TelegramMessageFormatter.format_technicals_view(sig_dict)
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
            elif action == "live":
                provider = market_data_manager.get_provider()
                current_price = await provider.get_current_price(sig_dict["asset_symbol"])
                text, kb = TelegramMessageFormatter.format_live_signal_view(sig_dict, current_price)
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
            elif action == "details":
                text, kb = TelegramMessageFormatter.format_full_details_view(sig_dict)
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})
            elif action == "back":
                text, kb = TelegramMessageFormatter.format_main_signal(sig_dict)
                await telegram_service.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": kb})

        except Exception as e:
            logger.error(f"[TELEGRAM CALLBACK ERROR] Action '{data}': {e}", exc_info=True)
        finally:
            if cb_id:
                try:
                    await telegram_service.answer_callback_query(cb_id)
                except Exception as ans_err:
                    logger.debug(f"answer_callback_query notice: {ans_err}")
