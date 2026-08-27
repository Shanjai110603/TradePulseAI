import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_async_engine(database_url: str):
    db_url = database_url
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Clean pgbouncer parameter from query string if present
    if "?pgbouncer=true" in db_url:
        db_url = db_url.replace("?pgbouncer=true", "")
    elif "&pgbouncer=true" in db_url:
        db_url = db_url.replace("&pgbouncer=true", "")

    engine_kwargs = {"echo": False}
    if "sqlite" in db_url:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    elif "postgresql" in db_url:
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = 1800
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20
        if "pooler.supabase.com" in db_url or "6543" in db_url:
            engine_kwargs["connect_args"] = {
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0
            }

    return create_async_engine(db_url, **engine_kwargs)


# Initialize Primary Engine
async_engine = build_async_engine(settings.DATABASE_URL)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base model class with standard fields"""
    pass


def utc_now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initializes the database schema and performs migrations for BigInteger telegram IDs.
    """
    global async_engine, AsyncSessionLocal
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully.")

        # Non-blocking PostgreSQL schema migration
        if "postgresql" in str(async_engine.url):
            try:
                async with async_engine.begin() as conn:
                    from sqlalchemy import text
                    await conn.execute(text("ALTER TABLE telegram_accounts ALTER COLUMN telegram_user_id TYPE BIGINT;"))
                    await conn.execute(text("ALTER TABLE telegram_accounts ALTER COLUMN telegram_chat_id TYPE BIGINT;"))
            except Exception as migration_err:
                logger.debug(f"PostgreSQL BigInt migration notice: {migration_err}")
    except Exception as e:
        logger.warning(f"Remote database connection failed ({e}). Falling back to local SQLite database...")
        fallback_url = "sqlite+aiosqlite:///./tradepulse.db"
        async_engine = build_async_engine(fallback_url)
        AsyncSessionLocal.configure(bind=async_engine)
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Local SQLite database initialized and active.")
