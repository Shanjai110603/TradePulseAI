import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, delete

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserPreferences
from app.models.pattern import Pattern, PatternVersion, PatternImage
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
    """Seeds default demo user and pre-configured Pattern Type 1 / 14 if DB is empty.
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

        # Seed Modern Institutional SMC & Quotex Strategies
        strategies_to_seed = [
            {
                "name": "SMC Liquidity Sweep",
                "description": "Smart Money Concepts: Detects stop-hunt liquidity grabs past key highs/lows with instant shadow rejection.",
                "direction": "DOWN",
                "type": "liquidity_sweep",
                "params": {"direction": "DOWN", "lookback": 15}
            },
            {
                "name": "SMC Fair Value Gap",
                "description": "Smart Money Concepts: Detects 3-candle price imbalance mitigation zones for high-probability entries.",
                "direction": "DOWN",
                "type": "fair_value_gap",
                "params": {"direction": "DOWN", "lookback": 10}
            },
            {
                "name": "SMC Break of Structure",
                "description": "Smart Money Concepts: Confirms structural swing break and trend expansion.",
                "direction": "DOWN",
                "type": "break_of_structure",
                "params": {"direction": "DOWN", "lookback": 20}
            },
            {
                "name": "SNR Wick Reversal",
                "description": "STRATEGY 1: SNR WICK REVERSAL - 5M candle wick ratio > 45% with S/R line touch within 0.05%, RSI filter, and BB rejection.",
                "direction": "DOWN",
                "type": "snr_wick_reversal",
                "params": {"direction": "DOWN", "min_wick_ratio": 0.45}
            },
            {
                "name": "EMA Trend Bounce",
                "description": "STRATEGY 2: EMA TREND BOUNCE - Trend continuation test & bounce at EMA 20 with EMA 200 filter and Stochastic confluence.",
                "direction": "DOWN",
                "type": "ema_trend_bounce",
                "params": {"direction": "DOWN", "ema_period": 20}
            },
            {
                "name": "MTF Momentum Alignment",
                "description": "STRATEGY 3: MULTI-TIMEFRAME MOMENTUM - 2 consecutive strong Marubozu momentum expansion candles beyond preceding extremes with MACD filter.",
                "direction": "DOWN",
                "type": "mtf_momentum",
                "params": {"direction": "DOWN"}
            }
        ]

        # Deactivate any legacy pattern templates
        legacy_patterns_res = await db.execute(
            select(Pattern).where(Pattern.name.in_(["Pattern Type 1", "Pattern Type 14", "Pattern Type 15", "Inverted Pattern Type 14"]))
        )
        for legacy_p in legacy_patterns_res.scalars().all():
            legacy_p.is_active = False

        for strat in strategies_to_seed:
            strat_res = await db.execute(
                select(Pattern).where(Pattern.user_id == demo_user.id, Pattern.name == strat["name"])
            )
            if not strat_res.scalar_one_or_none():
                logger.info(f"Seeding {strat['name']} strategy...")
                p_new = Pattern(
                    user_id=demo_user.id,
                    name=strat["name"],
                    description=strat["description"],
                    market_id="digital_options",
                    direction=strat["direction"],
                    timeframe="1M",
                    is_active=True,
                    current_version=1,
                    assets_config=["EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)", "USD/BRL (OTC)", "EUR/NZD (OTC)", "BTC/USDT (OTC)", "USD/ARS (OTC)"],
                    timeframes_config={"1M": "Any"},
                    trend_config={"required": "Any"},
                    momentum_config={"strength": "Any"},
                    volume_config={},
                    indicators_config=[],
                    rules_config={
                        "operator": "AND",
                        "conditions": [
                            {
                                "type": strat["type"],
                                "params": strat["params"]
                            }
                        ]
                    },
                    entry_config={"type": "immediate"},
                    target_config={"duration_type": "time", "duration_minutes": 1, "duration_candles": 1},
                    ai_config={"enabled": True, "min_score": 65, "min_confidence": "MODERATE", "required_bias": "ANY"},
                    notification_config={"telegram": True, "notify_on_entry": True, "notify_on_outcome": True}
                )
                db.add(p_new)
                await db.flush()

                v_new = PatternVersion(
                    pattern_id=p_new.id,
                    version_number=1,
                    change_summary=f"System reference {strat['name']}",
                    config_snapshot={
                        "name": p_new.name,
                        "direction": p_new.direction,
                        "timeframe": p_new.timeframe,
                        "market_id": p_new.market_id,
                        "rules_config": p_new.rules_config,
                        "target_config": p_new.target_config
                    }
                )
                db.add(v_new)
                logger.info(f"{strat['name']} seeded successfully.")
        await db.commit()

        # Purge legacy patterns so bot ONLY evaluates pure institutional strategies
        await db.execute(
            delete(Pattern).where(Pattern.name.in_(["Pattern Type 1", "Pattern Type 14", "Pattern Type 15", "Inverted Pattern Type 14", "Quotex 1M OTC Momentum", "Quotex 1M OTC Reversal"]))
        )
        await db.commit()



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing TradePulse AI Backend Database schema...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Error during init_db: {e}", exc_info=True)

    try:
        await seed_initial_data()
    except Exception as e:
        logger.error(f"Error during seed_initial_data: {e}", exc_info=True)

    try:
        background_scheduler.start()
    except Exception as e:
        logger.error(f"Error starting background scheduler: {e}", exc_info=True)

    try:
        telegram_poller.start()
    except Exception as e:
        logger.error(f"Error starting telegram poller: {e}", exc_info=True)

    yield
    # Shutdown
    try:
        telegram_poller.stop()
    except Exception:
        pass
    try:
        background_scheduler.stop()
    except Exception:
        pass


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
