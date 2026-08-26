import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, JSON, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class TelegramAccount(Base, TimestampMixin):
    __tablename__ = "telegram_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    muted_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="telegram_account")
    subscriptions: Mapped[List["SignalSubscription"]] = relationship("SignalSubscription", back_populates="telegram_account", cascade="all, delete-orphan")


class TelegramLinkCode(Base, TimestampMixin):
    __tablename__ = "telegram_link_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)


class SignalSubscription(Base, TimestampMixin):
    __tablename__ = "signal_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("telegram_accounts.id", ondelete="CASCADE"), nullable=False)
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False)
    notification_level: Mapped[str] = mapped_column(String(30), default="ALL")  # ALL, TARGETS, EXPIRY, COMPLETION_ONLY
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    telegram_account: Mapped["TelegramAccount"] = relationship("TelegramAccount", back_populates="subscriptions")
