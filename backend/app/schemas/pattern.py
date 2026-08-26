from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class PatternImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pattern_id: str
    file_path: str
    filename: str
    mime_type: str
    file_size_bytes: int
    description: Optional[str] = None
    is_primary: bool
    created_at: datetime


class PatternVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pattern_id: str
    version_number: int
    change_summary: Optional[str] = None
    config_snapshot: Dict[str, Any]
    created_at: datetime



class TrendConfig(BaseModel):
    required: str = "Any"  # Strong Bullish, Bullish, Neutral, Bearish, Strong Bearish, Any
    mtf: Dict[str, str] = Field(default_factory=dict)  # {"1M": "Any", "5M": "Bearish", "15M": "Bearish", "1H": "Any"}


class MomentumConfig(BaseModel):
    strength: str = "Any"  # Strong, Moderate, Weak, Any
    rsi_min: Optional[float] = 0.0
    rsi_max: Optional[float] = 100.0
    adx_min: Optional[float] = None
    macd_bias: Optional[str] = "Any"  # Bullish, Bearish, Any
    stoch_min: Optional[float] = None
    stoch_max: Optional[float] = None


class VolumeConfig(BaseModel):
    type: str = "Any"  # Any, above_average, confirming, strong
    min_pct_of_ma: Optional[float] = 100.0  # e.g., 120 means >= 120% of 20-period volume SMA


class IndicatorCriterion(BaseModel):
    indicator: str  # RSI, MACD, EMA_FAST, EMA_SLOW, SMA_200, BOLLINGER, VWAP, ATR, ADX
    condition: str  # ABOVE, BELOW, CROSS_ABOVE, CROSS_BELOW, BETWEEN, TOUCH_UPPER, TOUCH_LOWER
    value: Optional[float] = None
    secondary_value: Optional[float] = None
    period: Optional[int] = 14


class RuleConditionPrimitive(BaseModel):
    type: str  # candle_color, candle_sequence, support_break, resistance_break, indicator_cross, price_level
    params: Dict[str, Any] = Field(default_factory=dict)
    # Examples:
    # {"type": "candle_color", "params": {"index": -1, "color": "bearish"}}
    # {"type": "candle_sequence", "params": {"colors": ["bearish", "bullish", "bullish"]}}
    # {"type": "support_break", "params": {"lookback": 5, "break_type": "close_below", "level_source": "swing_low"}}


class CompositeRuleGroup(BaseModel):
    operator: str = "AND"  # AND, OR, NOT
    conditions: List[Union[RuleConditionPrimitive, Dict[str, Any]]] = Field(default_factory=list)


class EntryConfig(BaseModel):
    type: str = "immediate"  # immediate, pullback, breakout_close
    limit_offset_pips: Optional[float] = 0.0


class TargetConfig(BaseModel):
    # For digital-options-style:
    duration_type: str = "time"  # time | candle_count
    duration_minutes: Optional[int] = 5
    duration_candles: Optional[int] = 5
    # For standard markets:
    risk_reward_ratio: Optional[float] = 2.0
    stop_loss_pips: Optional[float] = None
    tp1_pips: Optional[float] = None
    tp2_pips: Optional[float] = None
    tp3_pips: Optional[float] = None


class AISettings(BaseModel):
    enabled: bool = True
    min_score: int = 75  # 0 - 100
    min_confidence: str = "MODERATE"  # LOW, MODERATE, HIGH
    required_bias: str = "ANY"  # BULLISH, BEARISH, ANY
    max_risk_level: str = "MODERATE"  # LOW, MODERATE, HIGH


class NotificationBehavior(BaseModel):
    telegram: bool = True
    notify_on_entry: bool = True
    notify_on_status_change: bool = True
    notify_on_outcome: bool = True


class PatternCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    market_id: str
    direction: str = "DOWN"  # UP, DOWN, LONG, SHORT, BUY, SELL
    timeframe: str = "1M"
    assets_config: List[str] = Field(default_factory=list)  # List of asset IDs/symbols
    timeframes_config: Dict[str, str] = Field(default_factory=dict)
    trend_config: TrendConfig = Field(default_factory=TrendConfig)
    momentum_config: MomentumConfig = Field(default_factory=MomentumConfig)
    volume_config: VolumeConfig = Field(default_factory=VolumeConfig)
    indicators_config: List[IndicatorCriterion] = Field(default_factory=list)
    rules_config: Dict[str, Any] = Field(default_factory=dict)
    entry_config: EntryConfig = Field(default_factory=EntryConfig)
    target_config: TargetConfig = Field(default_factory=TargetConfig)
    ai_config: AISettings = Field(default_factory=AISettings)
    notification_config: NotificationBehavior = Field(default_factory=NotificationBehavior)
    is_active: bool = True


class PatternUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    direction: Optional[str] = None
    timeframe: Optional[str] = None
    assets_config: Optional[List[str]] = None
    timeframes_config: Optional[Dict[str, str]] = None
    trend_config: Optional[TrendConfig] = None
    momentum_config: Optional[MomentumConfig] = None
    volume_config: Optional[VolumeConfig] = None
    indicators_config: Optional[List[IndicatorCriterion]] = None
    rules_config: Optional[Dict[str, Any]] = None
    entry_config: Optional[EntryConfig] = None
    target_config: Optional[TargetConfig] = None
    ai_config: Optional[AISettings] = None
    notification_config: Optional[NotificationBehavior] = None
    is_active: Optional[bool] = None
    change_summary: Optional[str] = None


class PatternResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    market_id: str
    direction: str
    timeframe: str
    is_active: bool
    current_version: int
    assets_config: List[str] = []
    timeframes_config: Dict[str, Any] = {}
    trend_config: Dict[str, Any] = {}
    momentum_config: Dict[str, Any] = {}
    volume_config: Dict[str, Any] = {}
    indicators_config: List[Dict[str, Any]] = []
    rules_config: Dict[str, Any] = {}
    entry_config: Dict[str, Any] = {}
    target_config: Dict[str, Any] = {}
    ai_config: Dict[str, Any] = {}
    notification_config: Dict[str, Any] = {}
    images: List[PatternImageResponse] = []
    created_at: datetime
    updated_at: datetime

    # Summary performance metrics for pattern cards
    total_signals: Optional[int] = 0
    win_rate: Optional[float] = 0.0
    last_signal_time: Optional[datetime] = None

