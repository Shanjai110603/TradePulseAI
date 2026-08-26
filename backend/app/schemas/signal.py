from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class SignalEventResponse(BaseModel):
    id: str
    signal_id: str
    event_type: str
    price: Optional[float] = None
    message: str
    data: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class SignalTechnicalSnapshotResponse(BaseModel):
    id: str
    signal_id: str
    rsi: Optional[float] = None
    macd: Dict[str, Any] = {}
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    sma_200: Optional[float] = None
    bollinger_bands: Dict[str, Any] = {}
    atr: Optional[float] = None
    adx: Optional[float] = None
    stochastic: Dict[str, Any] = {}
    vwap: Optional[float] = None
    volume_ratio: Optional[float] = None
    support_levels: List[float] = []
    resistance_levels: List[float] = []
    market_structure: Dict[str, Any] = {}
    mtf_summary: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class SignalAIAnalysisResponse(BaseModel):
    id: str
    signal_id: str
    ai_provider: str
    bias: str
    score: int
    confidence: str
    trend_assessment: str
    momentum_assessment: str
    volume_assessment: str
    structure_assessment: str
    entry_quality: str
    risk_assessment: str
    volatility: str
    key_levels: Dict[str, Any] = {}
    reasoning: str
    risks: List[str] = []
    invalidating_conditions: List[str] = []

    class Config:
        from_attributes = True


class SignalResultResponse(BaseModel):
    id: str
    signal_id: str
    outcome: str
    exit_price: float
    exit_time: datetime
    pnl_percentage: Optional[float] = None
    max_favorable_excursion: Optional[float] = None
    max_adverse_excursion: Optional[float] = None
    post_analysis_notes: Optional[str] = None

    class Config:
        from_attributes = True


class SignalResponse(BaseModel):
    id: str
    user_id: str
    pattern_id: Optional[str] = None
    pattern_version: int
    pattern_name: str
    market_id: str
    asset_symbol: str
    direction: str
    timeframe: str
    reference_price: float
    entry_time: datetime
    expiry_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    entry_price_min: Optional[float] = None
    entry_price_max: Optional[float] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    signal_strength: str
    ai_score: Optional[int] = None
    ai_confidence: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SignalDetailResponse(SignalResponse):
    technical_snapshot: Optional[SignalTechnicalSnapshotResponse] = None
    ai_analysis: Optional[SignalAIAnalysisResponse] = None
    result: Optional[SignalResultResponse] = None
    events: List[SignalEventResponse] = []
    raw_trigger_candles: List[Dict[str, Any]] = []
