from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.signal import Signal, SignalResult
from app.models.pattern import Pattern
from app.schemas.performance import PerformanceOverviewResponse, PatternPerformanceStat, AssetPerformanceStat, AIScoreCorrelationStat

router = APIRouter(prefix="/performance", tags=["Performance Analytics"])


@router.get("/overview", response_model=PerformanceOverviewResponse)
async def get_performance_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = current_user.id

    # ── Total & active signal counts ──────────────────────────────────────────
    total_signals = (await db.execute(
        select(func.count(Signal.id)).where(Signal.user_id == uid)
    )).scalar() or 0

    active_signals = (await db.execute(
        select(func.count(Signal.id)).where(Signal.user_id == uid, Signal.status == "ACTIVE")
    )).scalar() or 0

    active_patterns = (await db.execute(
        select(func.count(Pattern.id)).where(Pattern.user_id == uid, Pattern.is_active == True)
    )).scalar() or 0

    # ── Global win-rate from real SignalResult rows ───────────────────────────
    results_q = (
        select(SignalResult.outcome, func.count(SignalResult.id))
        .join(Signal, SignalResult.signal_id == Signal.id)
        .where(Signal.user_id == uid)
        .group_by(SignalResult.outcome)
    )
    res_rows = (await db.execute(results_q)).all()
    outcome_map = {row[0]: row[1] for row in res_rows}
    wins_total   = outcome_map.get("WIN",  0)
    losses_total = outcome_map.get("LOSS", 0)
    decided      = wins_total + losses_total
    overall_wr   = round(wins_total / decided * 100.0, 1) if decided > 0 else 0.0

    # ── Per-market win rates ──────────────────────────────────────────────────
    def _market_wr(market_id: str) -> float:
        # computed below from market_stats
        return 0.0

    market_results_q = (
        select(Signal.market_id, SignalResult.outcome, func.count(SignalResult.id))
        .join(SignalResult, SignalResult.signal_id == Signal.id)
        .where(Signal.user_id == uid)
        .group_by(Signal.market_id, SignalResult.outcome)
    )
    market_rows = (await db.execute(market_results_q)).all()
    market_outcome: dict = {}
    for mid, outcome, cnt in market_rows:
        market_outcome.setdefault(mid, {})
        market_outcome[mid][outcome] = cnt

    def _wr(m: dict) -> float:
        w = m.get("WIN", 0); l = m.get("LOSS", 0)
        return round(w / (w + l) * 100, 1) if (w + l) > 0 else 0.0

    digital_wr  = _wr(market_outcome.get("digital_options", {}))
    standard_wr = _wr(market_outcome.get("forex", market_outcome.get("crypto", {})))

    # ── Per-pattern performance ───────────────────────────────────────────────
    pat_q = (
        select(
            Signal.pattern_id,
            Signal.pattern_name,
            Signal.asset_symbol,
            Signal.timeframe,
            Signal.ai_score,
            SignalResult.outcome
        )
        .outerjoin(SignalResult, SignalResult.signal_id == Signal.id)
        .where(Signal.user_id == uid, Signal.pattern_id.isnot(None))
    )
    pat_rows = (await db.execute(pat_q)).all()

    pat_acc: dict = {}
    for pid, pname, asset, tf, ai_sc, outcome in pat_rows:
        if pid not in pat_acc:
            pat_acc[pid] = {"name": pname, "total": 0, "wins": 0, "losses": 0, "scores": [], "assets": {}}
        pat_acc[pid]["total"] += 1
        if outcome == "WIN":
            pat_acc[pid]["wins"] += 1
        elif outcome == "LOSS":
            pat_acc[pid]["losses"] += 1
        if ai_sc is not None:
            pat_acc[pid]["scores"].append(ai_sc)
        if asset:
            pat_acc[pid]["assets"][asset] = pat_acc[pid]["assets"].get(asset, 0) + 1

    pattern_stats = []
    for pid, d in pat_acc.items():
        w = d["wins"]; l = d["losses"]; dec = w + l
        wr = round(w / dec * 100, 1) if dec > 0 else 0.0
        best_asset = max(d["assets"], key=d["assets"].get) if d["assets"] else None
        avg_score = round(sum(d["scores"]) / len(d["scores"]), 1) if d["scores"] else None
        pattern_stats.append(PatternPerformanceStat(
            pattern_id=pid,
            pattern_name=d["name"],
            total_signals=d["total"],
            wins=w,
            losses=l,
            ties=d["total"] - dec,
            win_rate=wr,
            best_asset=best_asset,
            best_timeframe=None,
            average_ai_score=avg_score
        ))

    # Sort by win rate descending
    pattern_stats.sort(key=lambda x: x.win_rate, reverse=True)

    # ── Per-asset performance ─────────────────────────────────────────────────
    asset_q = (
        select(Signal.asset_symbol, Signal.market_id, SignalResult.outcome, func.count(SignalResult.id))
        .join(SignalResult, SignalResult.signal_id == Signal.id)
        .where(Signal.user_id == uid)
        .group_by(Signal.asset_symbol, Signal.market_id, SignalResult.outcome)
    )
    asset_rows = (await db.execute(asset_q)).all()
    asset_acc: dict = {}
    for sym, mid, outcome, cnt in asset_rows:
        key = (sym, mid)
        asset_acc.setdefault(key, {"wins": 0, "losses": 0})
        if outcome == "WIN":   asset_acc[key]["wins"]   += cnt
        if outcome == "LOSS":  asset_acc[key]["losses"] += cnt

    top_assets = []
    for (sym, mid), d in asset_acc.items():
        w = d["wins"]; l = d["losses"]; dec = w + l
        wr = round(w / dec * 100, 1) if dec > 0 else 0.0
        pf = round(w / l, 2) if l > 0 else None
        top_assets.append(AssetPerformanceStat(
            asset_symbol=sym,
            market_id=mid,
            total_signals=dec,
            win_rate=wr,
            profit_factor=pf
        ))
    top_assets.sort(key=lambda x: x.win_rate, reverse=True)
    top_assets = top_assets[:5]

    # ── AI Score correlation ──────────────────────────────────────────────────
    ai_q = (
        select(Signal.ai_score, SignalResult.outcome)
        .join(SignalResult, SignalResult.signal_id == Signal.id)
        .where(Signal.user_id == uid, Signal.ai_score.isnot(None))
    )
    ai_rows = (await db.execute(ai_q)).all()

    buckets: dict = {
        "90-100": {"wins": 0, "total": 0},
        "80-89":  {"wins": 0, "total": 0},
        "70-79":  {"wins": 0, "total": 0},
        "<70":    {"wins": 0, "total": 0},
    }
    for score, outcome in ai_rows:
        if score is None: continue
        if score >= 90:   bk = "90-100"
        elif score >= 80: bk = "80-89"
        elif score >= 70: bk = "70-79"
        else:             bk = "<70"
        buckets[bk]["total"] += 1
        if outcome == "WIN":
            buckets[bk]["wins"] += 1

    ai_correlation = []
    for bk, d in buckets.items():
        t = d["total"]; w = d["wins"]
        wr = round(w / t * 100, 1) if t > 0 else 0.0
        ai_correlation.append(AIScoreCorrelationStat(score_bucket=bk, total_signals=t, win_rate=wr))

    return PerformanceOverviewResponse(
        total_signals_all_time=total_signals,
        active_signals_count=active_signals,
        overall_win_rate=overall_wr,
        digital_options_win_rate=digital_wr,
        standard_markets_win_rate=standard_wr,
        total_active_patterns=active_patterns,
        pattern_stats=pattern_stats,
        top_assets=top_assets,
        ai_correlation=ai_correlation
    )
