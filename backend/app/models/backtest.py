import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, JSON, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Backtest(Base, TimestampMixin):
    __tablename__ = "backtests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pattern_id: Mapped[str] = mapped_column(String(36), ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False, index=True)
    pattern_version: Mapped[int] = mapped_column(Integer, default=1)
    market_id: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    candle_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED")  # PENDING, RUNNING, COMPLETED, FAILED

    # Performance Summaries
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    winning_signals: Mapped[int] = mapped_column(Integer, default=0)
    losing_signals: Mapped[int] = mapped_column(Integer, default=0)
    tie_signals: Mapped[int] = mapped_column(Integer, default=0)
    win_rate_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    max_drawdown_percentage: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    average_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, default=0.0)

    # Detailed Outputs
    signals_log: Mapped[dict] = mapped_column(JSON, default=list)  # List of trades with entry/exit/outcome
    equity_curve: Mapped[dict] = mapped_column(JSON, default=list)  # List of {"timestamp": ..., "equity": ...}
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship("User", back_populates="backtests")
    pattern: Mapped["Pattern"] = relationship("Pattern", back_populates="backtests")
