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

        # Seed Pattern Type 1 (SMC 10 Line Reversal)
        p1_res = await db.execute(
            select(Pattern).where(Pattern.user_id == demo_user.id, Pattern.name == "Pattern Type 1")
        )
        if not p1_res.scalar_one_or_none():
            logger.info("Seeding Pattern Type 1 template...")
            p1 = Pattern(
                user_id=demo_user.id,
                name="Pattern Type 1",
                description="If market forms two green candles followed by one red candle with normal bodies below the SMC 10 Line, the entry is a sure shot for a red candle in the opposite direction.",
                market_id="digital_options",
                direction="DOWN",
                timeframe="1M",
                is_active=True,
                current_version=1,
                assets_config=["EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)", "BTC/USDT (OTC)", "AUD/CAD (OTC)", "EUR/USD", "GBP/USD"],
                timeframes_config={"1M": "Any"},
                trend_config={"required": "Bearish"},
                momentum_config={"strength": "Strong", "rsi_min": 0, "rsi_max": 65},
                volume_config={},
                indicators_config=[
                    {"indicator": "SMC_10", "condition": "BELOW", "value": 0.0}
                ],
                rules_config={
                    "operator": "AND",
                    "conditions": [
                        {
                            "type": "pattern_type_1",
                            "params": {
                                "smc_period": 10
                            }
                        }
                    ]
                },
                entry_config={"type": "immediate"},
                target_config={"duration_type": "time", "duration_minutes": 1, "duration_candles": 1},
                ai_config={"enabled": True, "min_score": 75, "min_confidence": "HIGH", "required_bias": "BEARISH"},
                notification_config={"telegram": True, "notify_on_entry": True, "notify_on_outcome": True}
            )
            db.add(p1)
            await db.flush()

            # Attach visual reference image
            img = PatternImage(
                pattern_id=p1.id,
                file_path="/uploads/patterns/pattern_type_1.jpg",
                file_name="pattern_type_1.jpg",
                file_size=62995,
                mime_type="image/jpeg",
                is_primary=True,
                description="Visual reference for Pattern Type 1: 2 Green Candles + 1 Red Candle under SMC 10 Line"
            )
            db.add(img)

            v1 = PatternVersion(
                pattern_id=p1.id,
                version_number=1,
                change_summary="System reference Pattern Type 1 (SMC 10 Under)",
                config_snapshot={
                    "name": p1.name,
                    "direction": p1.direction,
                    "timeframe": p1.timeframe,
                    "market_id": p1.market_id,
                    "rules_config": p1.rules_config,
                    "target_config": p1.target_config
                }
            )
            db.add(v1)
            await db.commit()
            logger.info("Pattern Type 1 seeded successfully.")

        # Seed Pattern Type 15 (V-Pattern Resistance Rejection)
        p15_res = await db.execute(
            select(Pattern).where(Pattern.user_id == demo_user.id, Pattern.name == "Pattern Type 15")
        )
        if not p15_res.scalar_one_or_none():
            logger.info("Seeding Pattern Type 15 template...")
            p15 = Pattern(
                user_id=demo_user.id,
                name="Pattern Type 15",
                description="If market makes a movement in 'V' Pattern and breakout the horizontal line then a sure shot will take place in opposite direction.",
                market_id="digital_options",
                direction="DOWN",
                timeframe="1M",
                is_active=True,
                current_version=1,
                assets_config=["EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)", "BTC/USDT (OTC)", "AUD/CAD (OTC)", "EUR/USD", "GBP/USD"],
                timeframes_config={"1M": "Any"},
                trend_config={"required": "Any"},
                momentum_config={"strength": "Strong", "rsi_min": 0, "rsi_max": 75},
                volume_config={},
                indicators_config=[],
                rules_config={
                    "operator": "AND",
                    "conditions": [
                        {
                            "type": "pattern_type_15",
                            "params": {
                                "lookback": 10
                            }
                        }
                    ]
                },
                entry_config={"type": "immediate"},
                target_config={"duration_type": "time", "duration_minutes": 1, "duration_candles": 1},
                ai_config={"enabled": True, "min_score": 75, "min_confidence": "HIGH", "required_bias": "BEARISH"},
                notification_config={"telegram": True, "notify_on_entry": True, "notify_on_outcome": True}
            )
            db.add(p15)
            await db.flush()

            # Attach visual reference image
            img15 = PatternImage(
                pattern_id=p15.id,
                file_path="/uploads/patterns/pattern_type_15.jpg",
                file_name="pattern_type_15.jpg",
                file_size=68940,
                mime_type="image/jpeg",
                is_primary=True,
                description="Visual reference for Pattern Type 15: V-Pattern rally rejecting horizontal line with upper wick"
            )
            db.add(img15)

            v15 = PatternVersion(
                pattern_id=p15.id,
                version_number=1,
                change_summary="System reference Pattern Type 15 (V-Pattern Reversal)",
                config_snapshot={
                    "name": p15.name,
                    "direction": p15.direction,
                    "timeframe": p15.timeframe,
                    "market_id": p15.market_id,
                    "rules_config": p15.rules_config,
                    "target_config": p15.target_config
                }
            )
            db.add(v15)
            await db.commit()
            logger.info("Pattern Type 15 seeded successfully.")

        # Seed Pattern Type 14 only if it doesn't exist yet
        pat_res = await db.execute(
            select(Pattern).where(Pattern.user_id == demo_user.id, Pattern.name == "Pattern Type 14")
        )
        if not pat_res.scalar_one_or_none():
            logger.info("Seeding Pattern Type 14 template...")
            p14 = Pattern(
                user_id=demo_user.id,
                name="Pattern Type 14",
                description="Draw a Horizontal Line (SUPPORT LINE) between first 2 Green Candles after the Red Candle and wait for the market to break that support level with a Red candle then trade in the same direction.",
                market_id="digital_options",
                direction="DOWN",
                timeframe="1M",
                is_active=True,
                current_version=1,
                assets_config=["EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)", "BTC/USDT (OTC)", "AUD/CAD (OTC)", "EUR/USD", "GBP/USD"],
                timeframes_config={"1M": "Any"},
                trend_config={"required": "Bearish", "strong_breakout_candle": True},
                momentum_config={"strength": "Strong", "rsi_min": 0, "rsi_max": 60},
                volume_config={},
                indicators_config=[
                    {"indicator": "RSI", "condition": "BELOW", "value": 55.0, "period": 14}
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
                target_config={"duration_type": "time", "duration_minutes": 1, "duration_candles": 1},
                ai_config={"enabled": True, "min_score": 75, "min_confidence": "HIGH", "required_bias": "BEARISH"},
                notification_config={"telegram": True, "notify_on_entry": True, "notify_on_outcome": True}
            )
            db.add(p14)
            await db.flush()

            # Attach visual reference image
            img14 = PatternImage(
                pattern_id=p14.id,
                file_path="/uploads/patterns/pattern_type_14.jpg",
                file_name="pattern_type_14.jpg",
                file_size=73383,
                mime_type="image/jpeg",
                is_primary=True,
                description="Visual reference for Pattern Type 14: Horizontal Support Breakdown with Strong Red Candle"
            )
            db.add(img14)

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
                "target_config": p14.target_config
            }
            v1 = PatternVersion(
                pattern_id=p14.id,
                version_number=1,
                change_summary="System reference Pattern Type 14 (Horizontal Support Breakout)",
                config_snapshot=snapshot
            )
            db.add(v1)
            await db.commit()
            logger.info("Pattern Type 14 seeded successfully.")

        # Seed Quotex OTC High-Frequency Reversal Pattern
        q_res = await db.execute(
            select(Pattern).where(Pattern.user_id == demo_user.id, Pattern.name == "Quotex 1M OTC Momentum")
        )
        if not q_res.scalar_one_or_none():
            logger.info("Seeding Quotex 1M OTC Momentum pattern...")
            q_pat = Pattern(
                user_id=demo_user.id,
                name="Quotex 1M OTC Momentum",
                description="High-frequency 1-Minute OTC breakout with RSI divergence & EMA trend confirmation",
                market_id="digital_options",
                direction="UP",
                timeframe="1M",
                is_active=True,
                current_version=1,
                assets_config=["EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)", "BTC/USDT (OTC)"],
                timeframes_config={"1M": "Any"},
                trend_config={},
                momentum_config={"rsi_min": 45, "rsi_max": 100},
                volume_config={},
                indicators_config=[
                    {"indicator": "RSI", "condition": "ABOVE", "value": 48.0, "period": 14}
                ],
                rules_config={},
                entry_config={"type": "immediate"},
                target_config={"duration_type": "time", "duration_minutes": 5, "duration_candles": 5},
                ai_config={"enabled": True, "min_score": 75, "min_confidence": "HIGH", "required_bias": "BULLISH"},
                notification_config={"telegram": True, "notify_on_entry": True, "notify_on_outcome": True}
            )
            db.add(q_pat)
            await db.flush()

            q_v1 = PatternVersion(
                pattern_id=q_pat.id,
                version_number=1,
                change_summary="Quotex 1M OTC Momentum Strategy",
                config_snapshot={"name": q_pat.name, "direction": q_pat.direction, "market_id": q_pat.market_id}
            )
            db.add(q_v1)
            await db.commit()
            logger.info("Quotex 1M OTC Momentum seeded successfully.")

        # Seed Quotex OTC RSI Reversal (DOWN) Strategy
        rev_res = await db.execute(
            select(Pattern).where(Pattern.user_id == demo_user.id, Pattern.name == "Quotex 1M OTC Reversal")
        )
        if not rev_res.scalar_one_or_none():
            logger.info("Seeding Quotex 1M OTC Reversal pattern...")
            rev_pat = Pattern(
                user_id=demo_user.id,
                name="Quotex 1M OTC Reversal",
                description="Overbought rejection & swing high reversal for high-payout 1-Minute OTC options",
                market_id="digital_options",
                direction="DOWN",
                timeframe="1M",
                is_active=True,
                current_version=1,
                assets_config=["EUR/USD (OTC)", "GBP/USD (OTC)", "USD/JPY (OTC)", "AUD/CAD (OTC)"],
                timeframes_config={"1M": "Any"},
                trend_config={},
                momentum_config={"rsi_min": 0, "rsi_max": 55},
                volume_config={},
                indicators_config=[
                    {"indicator": "RSI", "condition": "BELOW", "value": 52.0, "period": 14}
                ],
                rules_config={},
                entry_config={"type": "immediate"},
                target_config={"duration_type": "time", "duration_minutes": 5, "duration_candles": 5},
                ai_config={"enabled": True, "min_score": 75, "min_confidence": "HIGH", "required_bias": "BEARISH"},
                notification_config={"telegram": True, "notify_on_entry": True, "notify_on_outcome": True}
            )
            db.add(rev_pat)
            await db.flush()

            rev_v1 = PatternVersion(
                pattern_id=rev_pat.id,
                version_number=1,
                change_summary="Quotex 1M OTC Reversal Strategy",
                config_snapshot={"name": rev_pat.name, "direction": rev_pat.direction, "market_id": rev_pat.market_id}
            )
            db.add(rev_v1)
            await db.commit()
            logger.info("Quotex 1M OTC Reversal seeded successfully.")



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
