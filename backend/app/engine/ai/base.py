from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AIAnalysisResult(BaseModel):
    bias: str = Field(..., description="BULLISH, BEARISH, or NEUTRAL")
    score: int = Field(..., ge=0, le=100, description="Overall confidence score from 0 to 100")
    confidence: str = Field(..., description="LOW, MODERATE, or HIGH")
    trend_assessment: str
    momentum_assessment: str
    volume_assessment: str
    structure_assessment: str
    entry_quality: str
    risk_assessment: str
    volatility: str
    key_levels: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    risks: List[str] = Field(default_factory=list)
    invalidating_conditions: List[str] = Field(default_factory=list)
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class PostSignalAIReview(BaseModel):
    was_pattern_detection_correct: bool
    conditions_present: List[str]
    conditions_failed: List[str]
    ai_alignment_score: int  # 0 to 100
    market_context_impact: str
    improvement_notes: str


class AIProvider(ABC):
    """Abstract interface for AI analysis providers"""

    @abstractmethod
    async def analyze_signal(
        self,
        candidate_data: Dict[str, Any],
        technical_snapshot: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None
    ) -> AIAnalysisResult:
        """Performs structured AI analysis on a validated deterministic signal candidate"""
        pass

    @abstractmethod
    async def post_signal_analysis(
        self,
        signal_data: Dict[str, Any],
        outcome_data: Dict[str, Any],
        historical_candles: List[Any]
    ) -> PostSignalAIReview:
        """Performs post-trade review analyzing reasons for win/loss"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns provider identifier name"""
        pass
