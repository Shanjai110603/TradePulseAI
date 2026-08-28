import time
import os
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func

from app.core.config import settings
from app.core.database import get_db
from app.api.auth import get_current_user, get_current_admin_user
from app.models.user import User
from app.models.signal import Signal
from app.models.pattern import Pattern
from app.schemas.admin import HealthStatusResponse, SystemMetricsResponse
from app.engine.market_data.manager import market_data_manager
from app.engine.ai.manager import ai_manager
from app.telegram.bot import telegram_service

router = APIRouter(prefix="/admin", tags=["Admin & Health"])
_start_time = time.time()


@router.get("/health", response_model=HealthStatusResponse)
async def get_health_status(db: AsyncSession = Depends(get_db)):
    # Test DB connection
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    provider = market_data_manager.get_provider()
    active_ai = ai_manager.get_provider()

    return HealthStatusResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc),
        database={"status": db_status, "url_type": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql"},
        redis={"status": "disabled_or_optional"},
        market_data_provider={
            "active_provider": provider.get_provider_name(),
            "is_live": provider.is_live(),
            "supported_timeframes": provider.get_supported_timeframes()
        },
        ai_provider={
            "active_provider": active_ai.get_provider_name(),
            "status": "ready"
        },
        telegram={
            "test_mode": telegram_service.test_mode,
            "bot_configured": bool(settings.TELEGRAM_BOT_TOKEN)
        },
        workers={
            "pattern_evaluator": "running",
            "signal_lifecycle_tracker": "running"
        }
    )


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    users_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    patterns_count = (await db.execute(select(func.count(Pattern.id)).where(Pattern.is_active == True))).scalar() or 0
    signals_count = (await db.execute(select(func.count(Signal.id)))).scalar() or 0

    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    signals_today_count = (await db.execute(
        select(func.count(Signal.id)).where(Signal.created_at >= today_start)
    )).scalar() or 0

    process = psutil.Process(os.getpid()) if hasattr(psutil, "Process") else None
    mem_mb = (process.memory_info().rss / 1024 / 1024) if process else 45.0

    return SystemMetricsResponse(
        total_users=users_count,
        total_active_patterns=patterns_count,
        total_signals_today=signals_today_count,
        total_signals_all_time=signals_count,
        uptime_seconds=time.time() - _start_time,
        memory_usage_mb=round(mem_mb, 2)
    )
