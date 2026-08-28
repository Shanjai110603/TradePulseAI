import uuid
from datetime import datetime, timedelta, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import generate_linking_code
from app.api.auth import get_current_user, get_current_admin_user
from app.models.user import User
from app.models.telegram import TelegramAccount, TelegramLinkCode
from app.models.signal import Signal
from app.schemas.telegram import TelegramLinkCodeResponse, TelegramStatusResponse, TelegramLinkRequest
from app.telegram.bot import telegram_service
from app.telegram.handlers import TelegramUpdateHandler
from app.telegram.poller import telegram_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Integration"])


@router.post("/link-code", response_model=TelegramLinkCodeResponse)
async def generate_telegram_link_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    code = generate_linking_code(6)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    link_record = TelegramLinkCode(
        user_id=current_user.id,
        code=code,
        expires_at=expires_at,
        is_used=False
    )
    db.add(link_record)
    await db.commit()

    bot_username = telegram_poller.bot_username or "TradePulseAIBot"
    deep_link = f"https://t.me/{bot_username}?start={code}"
    instructions = f"Send /link {code} to @{bot_username} on Telegram to connect your account."

    return TelegramLinkCodeResponse(
        code=code,
        expires_at=expires_at,
        bot_username=bot_username,
        deep_link=deep_link,
        instructions=instructions
    )


@router.get("/status", response_model=TelegramStatusResponse)
async def get_telegram_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(TelegramAccount).where(TelegramAccount.user_id == current_user.id)
    res = await db.execute(query)
    tg_acc = res.scalar_one_or_none()

    bot_username = telegram_poller.bot_username or "TradePulseAIBot"

    if tg_acc:
        return TelegramStatusResponse(
            is_linked=True,
            telegram_username=tg_acc.telegram_username,
            telegram_chat_id=tg_acc.telegram_chat_id,
            is_active=tg_acc.is_active,
            is_muted=tg_acc.is_muted,
            muted_until=tg_acc.muted_until,
            bot_username=bot_username,
            test_mode=telegram_service.test_mode
        )
    return TelegramStatusResponse(
        is_linked=False,
        telegram_username=None,
        telegram_chat_id=None,
        is_active=False,
        is_muted=False,
        muted_until=None,
        bot_username=bot_username,
        test_mode=telegram_service.test_mode
    )


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receives incoming updates from Telegram Webhook with secret token verification"""
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if settings.TELEGRAM_WEBHOOK_SECRET and secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret token")
    update = await request.json()
    await TelegramUpdateHandler.process_update(update, db)
    return {"ok": True}


@router.get("/subscribers")
async def get_telegram_subscribers(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns all active Telegram subscribers receiving signals (Admin Only)"""
    query = select(TelegramAccount).order_by(TelegramAccount.created_at.desc())
    res = await db.execute(query)
    subscribers = res.scalars().all()
    return [
        {
            "id": s.id,
            "telegram_user_id": s.telegram_user_id,
            "telegram_chat_id": s.telegram_chat_id,
            "telegram_username": s.telegram_username,
            "first_name": s.first_name,
            "is_active": s.is_active,
            "is_muted": s.is_muted,
            "created_at": s.created_at
        }
        for s in subscribers
    ]


@router.delete("/subscribers")
async def clear_all_subscribers(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Clears all subscribers from the database registry (Admin Only)"""
    from sqlalchemy import delete
    await db.execute(delete(TelegramAccount))
    await db.commit()
    return {"message": "All Telegram subscribers cleared successfully"}


@router.delete("/subscribers/{subscriber_id}")
async def delete_single_subscriber(
    subscriber_id: str,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Removes a single subscriber from the registry (Admin Only)"""
    from sqlalchemy import delete
    await db.execute(delete(TelegramAccount).where(TelegramAccount.id == subscriber_id))
    await db.commit()
    return {"message": "Subscriber removed successfully"}


@router.post("/test-notification")
async def trigger_test_notification(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Broadcasts a sample signal alert card to ALL active subscribers (Admin Only)"""
    query = select(TelegramAccount).where(
        TelegramAccount.is_active == True,
        TelegramAccount.is_muted == False
    )
    res = await db.execute(query)
    subscribers = res.scalars().all()

    if not subscribers:
        raise HTTPException(
            status_code=400, 
            detail="No active Telegram subscribers found. Open @Logutrader_bot on Telegram and send /start to auto-subscribe!"
        )

    # 1. Fetch latest real signal from DB if available
    sig_res = await db.execute(
        select(Signal)
        .options(selectinload(Signal.technical_snapshot), selectinload(Signal.ai_analysis))
        .order_by(Signal.created_at.desc())
        .limit(1)
    )
    real_sig = sig_res.scalar_one_or_none()

    if real_sig:
        signal_to_broadcast = {
            "id": real_sig.id,
            "asset_symbol": real_sig.asset_symbol,
            "direction": real_sig.direction,
            "reference_price": real_sig.reference_price,
            "entry_time": real_sig.entry_time,
            "expiry_time": real_sig.expiry_time,
            "duration_minutes": real_sig.duration_minutes,
            "pattern_name": real_sig.pattern_name,
            "pattern_version": real_sig.pattern_version,
            "ai_score": real_sig.ai_score,
            "signal_strength": real_sig.signal_strength,
            "status": real_sig.status,
            "market_id": real_sig.market_id,
            "timeframe": real_sig.timeframe,
            "feed_source": "Quotex Live Relay",
        }
    else:
        from app.engine.market_data.manager import market_data_manager
        from app.engine.charts.chart_generator import TradeChartGenerator
        provider = market_data_manager.get_provider("quotex")
        curr_price = await provider.get_current_price("USD/BRL (OTC)")
        candles = await provider.get_candles("USD/BRL (OTC)", timeframe="1M", limit=30, strict_live_only=False)
        tech = provider.compute_technical_snapshot(candles, curr_price) if candles else {}
        signal_to_broadcast = {
            "id": str(uuid.uuid4()),
            "asset_symbol": "USD/BRL (OTC)",
            "direction": "DOWN",
            "reference_price": curr_price,
            "entry_time": datetime.now(timezone.utc),
            "expiry_time": datetime.now(timezone.utc) + timedelta(minutes=1),
            "duration_minutes": 1,
            "pattern_name": "SMC Liquidity Sweep",
            "pattern_version": 1,
            "ai_score": 92,
            "signal_strength": "HIGH",
            "status": "ACTIVE",
            "market_id": "digital_options",
            "timeframe": "1M",
            "feed_source": "Quotex Live Relay",
            "technical_snapshot": tech,
        }

    dispatched = 0
    for sub in subscribers:
        try:
            await telegram_service.send_signal_notification(sub.telegram_chat_id, signal_to_broadcast)
            dispatched += 1
        except Exception as e:
            logger.error(f"Failed to dispatch signal to chat {sub.telegram_chat_id}: {e}")

    return {"message": f"Real-time signal alert card dispatched to {dispatched} subscriber(s)", "subscribers_count": dispatched}
