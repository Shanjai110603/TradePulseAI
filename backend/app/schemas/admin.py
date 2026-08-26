from typing import Dict, Any, List
from pydantic import BaseModel
from datetime import datetime


class HealthStatusResponse(BaseModel):
    status: str  # healthy, degraded, unhealthy
    version: str
    timestamp: datetime
    database: Dict[str, Any]
    redis: Dict[str, Any]
    market_data_provider: Dict[str, Any]
    ai_provider: Dict[str, Any]
    telegram: Dict[str, Any]
    workers: Dict[str, Any]


class SystemMetricsResponse(BaseModel):
    total_users: int
    total_active_patterns: int
    total_signals_today: int
    total_signals_all_time: int
    uptime_seconds: float
    memory_usage_mb: float
