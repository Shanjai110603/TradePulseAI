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

    # Database & Supabase Integration
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./tradepulse.db",
        description="SQLAlchemy database connection string"
    )
    REDIS_URL: Optional[str] = "redis://localhost:6339/0"
    SUPABASE_URL: Optional[str] = "https://gvtcspyomoxliglxuxjv.supabase.co"
    SUPABASE_KEY: Optional[str] = "sb_publishable_X7JOCS41pQfRRJt1aEYMdQ_RRD3sxP3"
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = ""

    # Security
    SECRET_KEY: str = "tradepulse_super_secret_jwt_key_change_in_production_2026_x89"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = "8862910637:AAHNwgv4MLBysPRscJ-V30HfC-QI74FgIjU"
    TELEGRAM_WEBHOOK_URL: Optional[str] = ""
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = ""
    TELEGRAM_TEST_MODE: bool = False  # False connects to real Telegram Bot

    # Market Data
    MARKET_DATA_PROVIDER: str = "quotex"  # mock | binance | quotex
    MARKET_DATA_API_KEY: Optional[str] = ""
    MARKET_POLL_INTERVAL_SECONDS: int = 10

    # Quotex Account Credentials
    QUOTEX_EMAIL: Optional[str] = "logeshpythonbot@gmail.com"
    QUOTEX_PASSWORD: Optional[str] = "BotForTraining@101"
    QUOTEX_SESSION_TOKEN: Optional[str] = ""

    # AI Provider
    AI_PROVIDER: str = "mock"  # Built-in deterministic quantitative AI engine
    AI_API_KEY: Optional[str] = ""
    OPENROUTER_API_KEY: Optional[str] = ""
    AI_MODEL: str = "openai/gpt-4o-mini"
    AI_TEMPERATURE: float = 0.2

    # Storage
    UPLOAD_DIR: str = "uploads/patterns"
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_IMAGE_TYPES: List[str] = ["image/png", "image/jpeg", "image/webp"]

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
