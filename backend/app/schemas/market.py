from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class MarketResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    market_type: str
    is_active: bool
    icon: Optional[str] = None
    features: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class DataSourceResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    is_active: bool
    is_live: bool
    is_free: bool
    supported_markets: List[str] = []
    rate_limit_per_minute: int

    class Config:
        from_attributes = True


class AssetResponse(BaseModel):
    id: str
    symbol: str
    base_asset: str
    quote_asset: str
    name: str
    market_id: str
    data_source_id: str
    is_active: bool
    price_precision: int
    min_movement: float

    class Config:
        from_attributes = True


class TimeframeResponse(BaseModel):
    id: str
    name: str
    seconds: int
    is_active: bool

    class Config:
        from_attributes = True


class CandleSchema(BaseModel):
    timestamp: int  # Unix timestamp in seconds or milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float

    class Config:
        from_attributes = True
