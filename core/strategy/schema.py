"""
TradePulse Custom Strategy Schema Definition
Pydantic data models defining user-created strategies, filters, and rule criteria.
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class TrendFilterConfig(BaseModel):
    enabled: bool = False
    mtf_timeframe: str = "5M"  # 5M or 15M
    ema_period: int = 20
    require_alignment: bool = True  # Green bar + close > EMA for CALL, Red + close < EMA for PUT


class CandleAnatomyConfig(BaseModel):
    min_body_ratio: float = 0.60  # e.g. 0.65 = 65% solid body
    max_opposing_wick: float = 0.35  # e.g. 0.30 = max 30% opposing wick
    filter_preceding_doji: bool = True  # Rejects preceding doji bars (<10% body)
    filter_spike_multiplier: float = 3.0  # Spike anomaly avoidance


class IndicatorRule(BaseModel):
    indicator: str  # RSI | EMA | MACD | STOCHASTIC | BOLLINGER | ATR | ADX | VWAP
    period: int = 14
    condition: str  # ABOVE | BELOW | BETWEEN | PRICE_ABOVE_CALL_BELOW_PUT
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    field: Optional[str] = None  # e.g. 'histogram', 'signal', 'percent_b', 'k'



class PriceActionConfig(BaseModel):
    require_engulfing: bool = False
    require_sr_breakout: bool = False
    min_sr_clearance_pct: float = 0.0  # e.g. 0.1% buffer from nearest opposing S/R


class SMCConfig(BaseModel):
    fvg_enabled: bool = False
    liquidity_sweep_enabled: bool = False
    bos_enabled: bool = False
    order_block_enabled: bool = False


class StrategyFilters(BaseModel):
    trend: TrendFilterConfig = Field(default_factory=TrendFilterConfig)
    candle_anatomy: CandleAnatomyConfig = Field(default_factory=CandleAnatomyConfig)
    indicators: List[IndicatorRule] = Field(default_factory=list)
    price_action: PriceActionConfig = Field(default_factory=PriceActionConfig)
    smc: SMCConfig = Field(default_factory=SMCConfig)


class UserStrategy(BaseModel):
    id: str
    name: str = "Custom Strategy"
    enabled: bool = True
    direction: Literal["CALL", "PUT", "BOTH"] = "BOTH"
    timeframe: str = "1M"
    expiry_minutes: int = 2
    min_payout: float = 80.0
    cooldown_seconds: int = 180
    assets: List[str] = Field(default_factory=lambda: ["ALL_MARKETS"])
    filters: StrategyFilters = Field(default_factory=StrategyFilters)
    martingale_mtg1: bool = False  # Next-candle continuation signal on loss
