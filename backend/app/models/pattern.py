import uuid
from typing import Optional, List
from sqlalchemy import String, Boolean, JSON, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Pattern(Base, TimestampMixin):
    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    market_id: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # UP, DOWN, LONG, SHORT, BUY, SELL, ANY
    timeframe: Mapped[str] = mapped_column(String(10), default="1M")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)

    # Rich Configuration Blobs
    assets_config: Mapped[dict] = mapped_column(JSON, default=list)  # List of asset symbols/IDs
    timeframes_config: Mapped[dict] = mapped_column(JSON, default=list)  # Multi-timeframe settings e.g. {"1M": "Any", "5M": "Bearish"}
    trend_config: Mapped[dict] = mapped_column(JSON, default=dict)  # {"required": "Bearish", "mtf": {"5M": "Bearish"}}
    momentum_config: Mapped[dict] = mapped_column(JSON, default=dict)  # {"rsi_min": 0, "rsi_max": 50, "adx_min": 20}
    volume_config: Mapped[dict] = mapped_column(JSON, default=dict)  # {"type": "above_average", "min_pct": 120}
    indicators_config: Mapped[dict] = mapped_column(JSON, default=list)  # List of indicator criteria
    rules_config: Mapped[dict] = mapped_column(JSON, default=dict)  # The deterministic AST rules tree (Candle sequence, S/R break, etc.)
    entry_config: Mapped[dict] = mapped_column(JSON, default=dict)  # {"type": "immediate"|"pullback", "distance": 0.0}
    target_config: Mapped[dict] = mapped_column(JSON, default=dict)  # Expiry duration (e.g. 5 min / 5 candles) or TP/SL
    ai_config: Mapped[dict] = mapped_column(JSON, default=dict)  # {"enabled": True, "min_score": 80, "bias": "BEARISH"}
    notification_config: Mapped[dict] = mapped_column(JSON, default=dict)  # {"telegram": True, "sound": True}

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="patterns")
    images: Mapped[List["PatternImage"]] = relationship("PatternImage", back_populates="pattern", cascade="all, delete-orphan")
    versions: Mapped[List["PatternVersion"]] = relationship("PatternVersion", back_populates="pattern", cascade="all, delete-orphan")
    signals: Mapped[List["Signal"]] = relationship("Signal", back_populates="pattern", cascade="all, delete-orphan")
    backtests: Mapped[List["Backtest"]] = relationship("Backtest", back_populates="pattern", cascade="all, delete-orphan")


class PatternImage(Base, TimestampMixin):
    __tablename__ = "pattern_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern_id: Mapped[str] = mapped_column(String(36), ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)

    pattern: Mapped["Pattern"] = relationship("Pattern", back_populates="images")


class PatternVersion(Base, TimestampMixin):
    __tablename__ = "pattern_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern_id: Mapped[str] = mapped_column(String(36), ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    pattern: Mapped["Pattern"] = relationship("Pattern", back_populates="versions")
