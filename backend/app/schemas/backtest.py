from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class BacktestRequest(BaseModel):
    pattern_id: str
    market_id: str
    asset_symbol: str
    timeframe: str = "1M"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    candle_count: int = 500  # Number of historical candles to replay


class BacktestTradeRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    candle_index: int
    direction: str
    entry_price: float
    exit_price: float
    exit_timestamp: datetime
    outcome: str  # WIN, LOSS, TIE
    pnl_percentage: float
    ai_score: Optional[int] = None
    duration_minutes: Optional[int] = None


class BacktestEquityPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    equity: float
    trade_number: int


class BacktestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    pattern_id: str
    pattern_version: int
    market_id: str
    asset_symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    candle_count: int
    status: str
    total_signals: int
    winning_signals: int
    losing_signals: int
    tie_signals: int
    win_rate_percentage: float
    profit_factor: Optional[float] = None
    max_drawdown_percentage: Optional[float] = None
    average_duration_seconds: Optional[float] = None
    created_at: datetime



class BacktestDetailResponse(BacktestResponse):
    signals_log: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
