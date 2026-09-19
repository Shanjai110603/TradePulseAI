"""
TradePulse Signal Model
Represents a confirmed trading signal with complete lifecycle status tracking
(ACTIVE -> EXPIRED -> WIN / LOSS / DRAW).
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Signal:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    strategy_name: str = "Custom Strategy"
    asset_symbol: str = "EUR/USD (OTC)"
    direction: str = "CALL"  # CALL or PUT
    timeframe: str = "1M"
    duration_minutes: int = 2
    entry_price: float = 0.0
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiry_time: Optional[datetime] = None
    live_payout: Optional[float] = None
    confidence: int = 85
    status: str = "ACTIVE"  # ACTIVE | WIN | LOSS | DRAW
    exit_price: Optional[float] = None
    audit_trail: Dict[str, Any] = field(default_factory=dict)
    chart_image_path: Optional[str] = None

    def __post_init__(self):
        if self.expiry_time is None and self.entry_time is not None:
            from datetime import timedelta
            self.expiry_time = self.entry_time + timedelta(minutes=self.duration_minutes)

    @property
    def is_call(self) -> bool:
        return self.direction.upper() in ["CALL", "UP", "BUY"]

    @property
    def is_put(self) -> bool:
        return self.direction.upper() in ["PUT", "DOWN", "SELL"]

    def evaluate_outcome(self, final_price: float) -> str:
        """Evaluates win/loss status based on exit price vs entry price with float epsilon tolerance."""
        self.exit_price = final_price
        diff = final_price - self.entry_price
        if abs(diff) < 1e-7:
            self.status = "DRAW"
        elif self.is_call:
            self.status = "WIN" if diff > 0 else "LOSS"
        else:  # PUT
            self.status = "WIN" if diff < 0 else "LOSS"
        return self.status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "asset_symbol": self.asset_symbol,
            "direction": self.direction,
            "timeframe": self.timeframe,
            "duration_minutes": self.duration_minutes,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "expiry_time": self.expiry_time.isoformat() if self.expiry_time else None,
            "live_payout": self.live_payout,
            "confidence": self.confidence,
            "status": self.status,
            "exit_price": self.exit_price,
            "audit_trail": self.audit_trail,
            "chart_image_path": self.chart_image_path,
        }
