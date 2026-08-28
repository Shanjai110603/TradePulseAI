from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.pattern import Pattern
from app.models.backtest import Backtest
from app.schemas.backtest import BacktestRequest, BacktestResponse, BacktestDetailResponse
from app.engine.market_data.manager import market_data_manager
from app.engine.backtesting.engine import BacktestingEngine

router = APIRouter(prefix="/backtests", tags=["Backtesting"])


@router.post("/run", response_model=BacktestDetailResponse)
async def run_backtest(
    req: BacktestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Pattern).where(Pattern.id == req.pattern_id, Pattern.user_id == current_user.id)
    res = await db.execute(query)
    pattern = res.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    provider = market_data_manager.get_provider()
    candles = await provider.get_candles(req.asset_symbol, timeframe=req.timeframe, limit=req.candle_count, strict_live_only=False)

    pattern_dict = {
        "id": pattern.id,
        "name": pattern.name,
        "market_id": req.market_id,
        "direction": pattern.direction,
        "timeframe": req.timeframe,
        "asset_symbol": req.asset_symbol,
        "trend_config": pattern.trend_config,
        "momentum_config": pattern.momentum_config,
        "volume_config": pattern.volume_config,
        "indicators_config": pattern.indicators_config,
        "rules_config": pattern.rules_config,
        "entry_config": pattern.entry_config,
        "target_config": pattern.target_config,
        "ai_config": pattern.ai_config,
    }

    result = await BacktestingEngine.run_backtest(pattern_dict, candles)

    start_dt = datetime.fromtimestamp(candles[0].timestamp, tz=timezone.utc) if candles else datetime.now(timezone.utc)
    end_dt = datetime.fromtimestamp(candles[-1].timestamp, tz=timezone.utc) if candles else datetime.now(timezone.utc)

    backtest_record = Backtest(
        user_id=current_user.id,
        pattern_id=pattern.id,
        pattern_version=pattern.current_version,
        market_id=req.market_id,
        asset_symbol=req.asset_symbol,
        timeframe=req.timeframe,
        start_date=start_dt,
        end_date=end_dt,
        candle_count=len(candles),
        status="COMPLETED",
        total_signals=result["total_signals"],
        winning_signals=result["winning_signals"],
        losing_signals=result["losing_signals"],
        tie_signals=result["tie_signals"],
        win_rate_percentage=result["win_rate_percentage"],
        profit_factor=result.get("profit_factor", 0.0),
        max_drawdown_percentage=result.get("max_drawdown_percentage", 0.0),
        average_duration_seconds=result.get("average_duration_seconds", 0.0),
        signals_log=result["signals_log"],
        equity_curve=result["equity_curve"],
        metrics=result.get("metrics", {})
    )
    db.add(backtest_record)
    await db.commit()
    await db.refresh(backtest_record)

    return backtest_record


@router.get("/pattern/{pattern_id}", response_model=List[BacktestResponse])
async def list_pattern_backtests(
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Backtest)
        .where(Backtest.pattern_id == pattern_id, Backtest.user_id == current_user.id)
        .order_by(desc(Backtest.created_at))
    )
    res = await db.execute(query)
    return res.scalars().all()


@router.get("/{backtest_id}", response_model=BacktestDetailResponse)
async def get_backtest_detail(
    backtest_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Backtest).where(Backtest.id == backtest_id, Backtest.user_id == current_user.id)
    res = await db.execute(query)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return record
