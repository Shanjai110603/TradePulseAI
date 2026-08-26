import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserPreferences
from app.models.pattern import Pattern, PatternVersion
from app.api.auth import router as auth_router
from app.api.markets import router as markets_router
from app.api.patterns import router as patterns_router
from app.api.pattern_rules import router as pattern_rules_router
from app.api.signals import router as signals_router
from app.api.backtests import router as backtests_router
from app.api.telegram import router as telegram_router
from app.api.performance import router as performance_router
from app.api.admin import router as admin_router
from app.workers.scheduler import background_scheduler
from app.telegram.poller import telegram_poller

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tradepulse")


async def seed_initial_data():
    """Seeds default demo user and pre-configured Pattern Type 14 if DB is empty.
    Also refreshes demo user password hash on every startup.
    """
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == "demo@tradepulse.ai"))
        demo_user = res.scalar_one_or_none()

        if not demo_user:
            logger.info("Seeding demo user...")
            demo_user = User(
                email="demo@tradepulse.ai",
                hashed_password=get_password_hash("password123"),
                full_name="Alex Mercer",
                is_admin=True,
                is_active=True
            )
            db.add(demo_user)
            await db.flush()

            prefs = UserPreferences(user_id=demo_user.id)
            db.add(prefs)
            await db.commit()
            await db.refresh(demo_user)
            logger.info(f"Demo user created with id={demo_user.id}")
        else:
            # Always refresh password hash on startup (ensures it matches native bcrypt)
            logger.info(f"Refreshing demo user password hash (id={demo_user.id})...")
            demo_user.hashed_password = get_password_hash("password123")
            demo_user.is_active = True
            db.add(demo_user)
            await db.commit()
            logger.info("Demo user password hash refreshed.")

        # Seed Pattern Type 14 only if it doesn't exist yet
        pat_res = await db.execute(
            select(Pattern).where(Pattern.user_id == demo_user.id, Pattern.name == "Pattern Type 14")
        )
        if not pat_res.scalar_one_or_none():
            logger.info("Seeding Pattern Type 14 template...")
            p14 = Pattern(
                user_id=demo_user.id,
                name="Pattern Type 14",
                description="Bearish initial candle -> 2 Bullish base candles creating support -> Bearish pullback -> Support close breakdown -> DOWN Signal",
                market_id="digital_options",
                direction="DOWN",
                timeframe="1M",
                is_active=True,
                current_version=1,
                assets_config=["EUR/USD", "GBP/USD", "USD/JPY"],
                timeframes_config={"1M": "Any", "5M": "Bearish"},
                trend_config={"required": "Bearish", "mtf": {"5M": "Bearish"}},
                momentum_config={"strength": "Strong", "rsi_min": 0, "rsi_max": 50, "adx_min": 20, "macd_bias": "Bearish"},
                volume_config={"type": "above_average", "min_pct_of_ma": 120},
                indicators_config=[
                    {"indicator": "RSI", "condition": "BELOW", "value": 50.0, "period": 14}
                ],
                rules_config={
                    "operator": "AND",
                    "conditions": [
                        {
                            "type": "pattern_type_14",
                            "params": {
                                "bullish_count": 2,
                                "confirmation": "close_below",
                                "support_source": "swing_low"
                            }
                        }
                    ]
                },
                entry_config={"type": "immediate"},
                target_config={"duration_type": "time", "duration_minutes": 5, "duration_candles": 5},
                ai_config={"enabled": True, "min_score": 80, "min_confidence": "HIGH", "required_bias": "BEARISH"},
                notification_config={"telegram": True, "notify_on_entry": True, "notify_on_outcome": True}
            )
            db.add(p14)
            await db.flush()

            snapshot = {
                "name": p14.name,
                "direction": p14.direction,
                "timeframe": p14.timeframe,
                "market_id": p14.market_id,
                "assets_config": p14.assets_config,
                "timeframes_config": p14.timeframes_config,
                "trend_config": p14.trend_config,
                "momentum_config": p14.momentum_config,
                "volume_config": p14.volume_config,
                "indicators_config": p14.indicators_config,
                "rules_config": p14.rules_config,
                "entry_config": p14.entry_config,
                "target_config": p14.target_config,
                "ai_config": p14.ai_config,
                "notification_config": p14.notification_config
            }
            v1 = PatternVersion(
                pattern_id=p14.id,
                version_number=1,
                change_summary="System reference Pattern Type 14",
                config_snapshot=snapshot
            )
            db.add(v1)
            await db.commit()
            logger.info("Pattern Type 14 seeded successfully.")



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing TradePulse AI Backend Database schema...")
    await init_db()
    await seed_initial_data()
    background_scheduler.start()
    telegram_poller.start()
    yield
    # Shutdown
    telegram_poller.stop()
    background_scheduler.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Powered Personalized Market Research & Telegram Signal Notification Platform",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for pattern image uploads
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include Routers
api_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_prefix)
app.include_router(markets_router, prefix=api_prefix)
app.include_router(patterns_router, prefix=api_prefix)
app.include_router(pattern_rules_router, prefix=api_prefix)
app.include_router(signals_router, prefix=api_prefix)
app.include_router(backtests_router, prefix=api_prefix)
app.include_router(telegram_router, prefix=api_prefix)
app.include_router(performance_router, prefix=api_prefix)
app.include_router(admin_router, prefix=api_prefix)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs": "/docs"
    }
