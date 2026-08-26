import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "TradePulse AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    # Supports Postgres or auto SQLite async fallback
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./tradepulse.db",
        description="SQLAlchemy database connection string"
    )
    REDIS_URL: Optional[str] = "redis://localhost:6339/0"

    # Security
    SECRET_KEY: str = "tradepulse_super_secret_jwt_key_change_in_production_2026_x89"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = ""
    TELEGRAM_WEBHOOK_URL: Optional[str] = ""
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = ""
    TELEGRAM_TEST_MODE: bool = True  # True enables local simulated Telegram test notifications

    # Market Data
    MARKET_DATA_PROVIDER: str = "mock"  # mock | binance | custom
    MARKET_DATA_API_KEY: Optional[str] = ""
    MARKET_POLL_INTERVAL_SECONDS: int = 5

    # AI Provider
    AI_PROVIDER: str = "mock"  # mock | openai | anthropic | gemini
    AI_API_KEY: Optional[str] = ""
    AI_MODEL: str = "gpt-4o-mini"
    AI_TEMPERATURE: float = 0.2

    # Storage
    UPLOAD_DIR: str = "uploads/patterns"
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_IMAGE_TYPES: List[str] = ["image/png", "image/jpeg", "image/webp"]

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
