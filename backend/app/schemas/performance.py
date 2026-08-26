from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime


class PatternPerformanceStat(BaseModel):
    pattern_id: str
    pattern_name: str
    total_signals: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    best_asset: Optional[str] = None
    best_timeframe: Optional[str] = None
    average_ai_score: Optional[float] = None


class AssetPerformanceStat(BaseModel):
    asset_symbol: str
    market_id: str
    total_signals: int
    win_rate: float
    profit_factor: Optional[float] = None


class AIScoreCorrelationStat(BaseModel):
    score_bucket: str  # e.g., "90-100", "80-89", "70-79", "<70"
    total_signals: int
    win_rate: float


class PerformanceOverviewResponse(BaseModel):
    total_signals_all_time: int
    active_signals_count: int
    overall_win_rate: float
    digital_options_win_rate: float
    standard_markets_win_rate: float
    total_active_patterns: int
    pattern_stats: List[PatternPerformanceStat] = []
    top_assets: List[AssetPerformanceStat] = []
    ai_correlation: List[AIScoreCorrelationStat] = []
