from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.signal import Signal, SignalEvent, SignalTechnicalSnapshot, SignalAIAnalysis, SignalResult
from app.schemas.signal import SignalResponse, SignalDetailResponse, SignalTechnicalSnapshotResponse, SignalAIAnalysisResponse, SignalResultResponse

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("", response_model=List[SignalResponse])
async def list_signals(
    market_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    pattern_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Signal).where(Signal.user_id == current_user.id)
    if market_id:
        query = query.where(Signal.market_id == market_id)
    if status:
        query = query.where(Signal.status == status)
    if pattern_id:
        query = query.where(Signal.pattern_id == pattern_id)

    query = query.order_by(desc(Signal.created_at)).limit(limit)
    res = await db.execute(query)
    return res.scalars().all()


@router.get("/{signal_id}", response_model=SignalDetailResponse)
async def get_signal_detail(
    signal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Signal)
        .where(Signal.id == signal_id, Signal.user_id == current_user.id)
        .options(
            selectinload(Signal.technical_snapshot),
            selectinload(Signal.ai_analysis),
            selectinload(Signal.result),
            selectinload(Signal.events)
        )
    )
    res = await db.execute(query)
    signal = res.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@router.get("/{signal_id}/technicals", response_model=SignalTechnicalSnapshotResponse)
async def get_signal_technicals(
    signal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(SignalTechnicalSnapshot).where(SignalTechnicalSnapshot.signal_id == signal_id)
    res = await db.execute(query)
    snap = res.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Technical snapshot not found")
    return snap


@router.get("/{signal_id}/analysis", response_model=SignalAIAnalysisResponse)
async def get_signal_ai_analysis(
    signal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(SignalAIAnalysis).where(SignalAIAnalysis.signal_id == signal_id)
    res = await db.execute(query)
    ai_snap = res.scalar_one_or_none()
    if not ai_snap:
        raise HTTPException(status_code=404, detail="AI Analysis not found")
    return ai_snap
