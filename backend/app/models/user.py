import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Relationships
    preferences: Mapped[Optional["UserPreferences"]] = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    telegram_account: Mapped[Optional["TelegramAccount"]] = relationship("TelegramAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")
    patterns: Mapped[List["Pattern"]] = relationship("Pattern", back_populates="user", cascade="all, delete-orphan")
    signals: Mapped[List["Signal"]] = relationship("Signal", back_populates="user", cascade="all, delete-orphan")
    backtests: Mapped[List["Backtest"]] = relationship("Backtest", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class UserPreferences(Base, TimestampMixin):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Global filter preferences
    default_market_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    min_ai_score: Mapped[int] = mapped_column(default=70)
    min_confidence: Mapped[str] = mapped_column(String(20), default="MODERATE")  # LOW, MODERATE, HIGH
    allowed_risk_levels: Mapped[dict] = mapped_column(JSON, default=lambda: ["LOW", "MODERATE", "HIGH"])
    notify_on_all_signals: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_status_change: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_outcome: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # "22:00"
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)    # "08:00"

    user: Mapped["User"] = relationship("User", back_populates="preferences")


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="sessions")
