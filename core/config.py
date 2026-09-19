"""
TradePulse Configuration Module
Loads settings from .env file and environment variables with sensible defaults.
"""
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "TradePulse"
    VERSION: str = "2.0.0"

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram bot API token")
    TELEGRAM_CHAT_IDS: str = Field(default="", description="Comma-separated chat/channel IDs for signal broadcasts")
    TELEGRAM_ADMIN_CHAT_IDS: str = Field(default="", description="Comma-separated chat IDs authorized to run admin commands")

    # Local Webhook Relay
    WEBHOOK_TOKEN: str = Field(default="", description="Shared secret token for authenticating webhook requests")

    # Quotex Credentials & Session
    QUOTEX_EMAIL: str = Field(default="", description="Quotex login email")
    QUOTEX_PASSWORD: str = Field(default="", description="Quotex login password")
    QUOTEX_SESSION_TOKEN: str = Field(default="", description="Quotex session token/cookie")
    QUOTEX_PROXY: str = Field(default="", description="HTTP/SOCKS5 proxy URL for VPS datacenter routing")

    # Regional WebSocket Failover Endpoints
    QUOTEX_WS_MIRRORS: str = Field(
        default=(
            "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket,"
            "wss://ws.market-qx.pro/socket.io/?EIO=3&transport=websocket,"
            "wss://ws.quotex.io/socket.io/?EIO=3&transport=websocket,"
            "wss://ws.broker-qx.pro/socket.io/?EIO=3&transport=websocket"
        ),
        description="Comma-separated WebSocket endpoint mirrors"
    )

    # Storage & Persistence
    DATA_DIR: str = Field(default=str(Path.home() / ".tradepulse"), description="Data storage folder")
    MIN_PAYOUT_THRESHOLD: int = Field(default=80, description="Minimum payout % threshold")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Trader Enhancements & Safeguards
    OTC_FLATLINE_GUARD: bool = Field(default=True, description="Filter out stagnant OTC flatline candles")
    PRE_ALERTS_ENABLED: bool = Field(default=True, description="Enable 15s pre-signal alerts before candle close")
    VOICE_ALERTS_ENABLED: bool = Field(default=True, description="Enable voice text-to-speech audio announcements")
    CONFLUENCE_SCANNER_ENABLED: bool = Field(default=True, description="Group multi-strategy confirmations into Ultra Confluence Signals")
    TELEGRAM_COMMANDS_ENABLED: bool = Field(default=True, description="Enable 2-way Telegram bot commands")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

    @property
    def chat_id_list(self) -> List[str]:
        """Returns parsed list of broadcast subscriber chat IDs."""
        if not self.TELEGRAM_CHAT_IDS:
            return []
        return [cid.strip() for cid in self.TELEGRAM_CHAT_IDS.split(",") if cid.strip()]

    @property
    def admin_chat_id_list(self) -> List[str]:
        """Returns parsed list of authorized admin chat IDs."""
        if not self.TELEGRAM_ADMIN_CHAT_IDS:
            return []
        return [cid.strip() for cid in self.TELEGRAM_ADMIN_CHAT_IDS.split(",") if cid.strip()]

    @property
    def ws_endpoints(self) -> List[str]:
        """Returns parsed list of WebSocket endpoints."""
        return [url.strip() for url in self.QUOTEX_WS_MIRRORS.split(",") if url.strip()]

    @property
    def resolved_data_dir(self) -> Path:
        """Returns Path object for resolved data directory and ensures it exists."""
        p = Path(self.DATA_DIR).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
