import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, JSON, Integer, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Signal(Base, TimestampMixin):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pattern_id: Mapped[str] = mapped_column(String(36), ForeignKey("patterns.id", ondelete="SET NULL"), nullable=True, index=True)
    pattern_version: Mapped[int] = mapped_column(Integer, default=1)
    pattern_name: Mapped[str] = mapped_column(String(100), nullable=False)

    market_id: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_symbol: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # UP, DOWN, LONG, SHORT, BUY, SELL
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)

    # Prices and Timing
    reference_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Standard Market Targets (where applicable)
    entry_price_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_price_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_reward_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metrics
    signal_strength: Mapped[str] = mapped_column(String(20), default="MODERATE")  # LOW, MODERATE, HIGH, VERY_HIGH
    ai_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0 - 100
    ai_confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # LOW, MODERATE, HIGH
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")  # GENERATED, PENDING, ACTIVE, UPDATE, EXPIRED, COMPLETED, INVALIDATED, CANCELLED

    # Deterministic Audit Trails
    matched_candle_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_trigger_candles: Mapped[dict] = mapped_column(JSON, default=list)  # Exact candles used to trigger

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="signals")
    pattern: Mapped[Optional["Pattern"]] = relationship("Pattern", back_populates="signals")
    events: Mapped[List["SignalEvent"]] = relationship("SignalEvent", back_populates="signal", cascade="all, delete-orphan")
    technical_snapshot: Mapped[Optional["SignalTechnicalSnapshot"]] = relationship("SignalTechnicalSnapshot", back_populates="signal", uselist=False, cascade="all, delete-orphan")
    ai_analysis: Mapped[Optional["SignalAIAnalysis"]] = relationship("SignalAIAnalysis", back_populates="signal", uselist=False, cascade="all, delete-orphan")
    result: Mapped[Optional["SignalResult"]] = relationship("SignalResult", back_populates="signal", uselist=False, cascade="all, delete-orphan")


class SignalEvent(Base, TimestampMixin):
    __tablename__ = "signal_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # GENERATED, NOTIFIED, STATUS_CHANGE, PRICE_TICK, TARGET_HIT, EXPIRED
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="events")


class SignalTechnicalSnapshot(Base, TimestampMixin):
    __tablename__ = "signal_technical_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id", ondelete="CASCADE"), unique=True, nullable=False)
    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd: Mapped[dict] = mapped_column(JSON, default=dict)  # {"macd": 0.1, "signal": 0.05, "hist": 0.05}
    ema_fast: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_slow: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_200: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bollinger_bands: Mapped[dict] = mapped_column(JSON, default=dict)
    atr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adx: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stochastic: Mapped[dict] = mapped_column(JSON, default=dict)
    vwap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    support_levels: Mapped[dict] = mapped_column(JSON, default=list)
    resistance_levels: Mapped[dict] = mapped_column(JSON, default=list)
    market_structure: Mapped[dict] = mapped_column(JSON, default=dict)
    mtf_summary: Mapped[dict] = mapped_column(JSON, default=dict)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="technical_snapshot")


class SignalAIAnalysis(Base, TimestampMixin):
    __tablename__ = "signal_ai_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id", ondelete="CASCADE"), unique=True, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    bias: Mapped[str] = mapped_column(String(20), nullable=False)  # BULLISH, BEARISH, NEUTRAL
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)  # LOW, MODERATE, HIGH
    trend_assessment: Mapped[str] = mapped_column(String(100), nullable=False)
    momentum_assessment: Mapped[str] = mapped_column(String(100), nullable=False)
    volume_assessment: Mapped[str] = mapped_column(String(100), nullable=False)
    structure_assessment: Mapped[str] = mapped_column(String(100), nullable=False)
    entry_quality: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_assessment: Mapped[str] = mapped_column(String(100), nullable=False)
    volatility: Mapped[str] = mapped_column(String(50), nullable=False)
    key_levels: Mapped[dict] = mapped_column(JSON, default=dict)  # {"support": [...], "resistance": [...]}
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    risks: Mapped[dict] = mapped_column(JSON, default=list)
    invalidating_conditions: Mapped[dict] = mapped_column(JSON, default=list)
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="ai_analysis")


class SignalResult(Base, TimestampMixin):
    __tablename__ = "signal_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id", ondelete="CASCADE"), unique=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # WIN, LOSS, TIE, INVALIDATED
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pnl_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_favorable_excursion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # MFE
    max_adverse_excursion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)     # MAE
    post_analysis_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="result")
