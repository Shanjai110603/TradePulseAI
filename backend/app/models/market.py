import uuid
from typing import Optional, List
from sqlalchemy import String, Boolean, JSON, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Market(Base, TimestampMixin):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "digital_options", "crypto", "forex", "stocks"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    market_type: Mapped[str] = mapped_column(String(50), nullable=False)  # DIGITAL_OPTIONS_STYLE, CRYPTO, FOREX, STOCKS, INDICES, COMMODITIES, FUTURES, OPTIONS
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    features: Mapped[dict] = mapped_column(JSON, default=dict)  # {"supports_expiry": True, "supports_sl_tp": True}

    # Relationships
    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="market", cascade="all, delete-orphan")


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "mock", "binance", "alpha_vantage"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)  # mock, live, delayed, historical
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True)
    supported_markets: Mapped[dict] = mapped_column(JSON, default=list)  # ["crypto", "forex"]
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=120)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., "crypto:BTC/USDT", "digital_options:EUR/USD"
    symbol: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # "BTC/USDT", "EUR/USD"
    base_asset: Mapped[str] = mapped_column(String(20), nullable=False)  # "BTC", "EUR"
    quote_asset: Mapped[str] = mapped_column(String(20), nullable=False)  # "USDT", "USD"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market_id: Mapped[str] = mapped_column(String(50), ForeignKey("markets.id", ondelete="CASCADE"), nullable=False)
    data_source_id: Mapped[str] = mapped_column(String(50), default="mock")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    price_precision: Mapped[int] = mapped_column(Integer, default=5)
    min_movement: Mapped[float] = mapped_column(Float, default=0.00001)

    market: Mapped["Market"] = relationship("Market", back_populates="assets")


class Timeframe(Base):
    __tablename__ = "timeframes"

    id: Mapped[str] = mapped_column(String(10), primary_key=True)  # "1M", "5M", "15M", "30M", "1H", "4H", "1D"
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
