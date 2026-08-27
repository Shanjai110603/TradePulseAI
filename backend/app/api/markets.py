from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.market import Market, Asset, DataSource, Timeframe
from app.schemas.market import MarketResponse, AssetResponse, DataSourceResponse, TimeframeResponse, CandleSchema, TickerItem
from app.engine.market_data.manager import market_data_manager

router = APIRouter(prefix="/markets", tags=["Markets & Assets"])


@router.get("/tickers", response_model=List[TickerItem])
async def get_live_tickers():
    provider = market_data_manager.get_provider()
    watch_symbols = [
        ("EUR/USD (OTC)", 5),
        ("BTC/USDT (OTC)", 2),
        ("GBP/USD (OTC)", 5),
        ("USD/JPY (OTC)", 3),
        ("AUD/CAD (OTC)", 5),
    ]
    tickers = []
    for sym, prec in watch_symbols:
        try:
            candles = await provider.get_candles(sym, timeframe="1M", limit=2)
            if len(candles) >= 2:
                prev_c = candles[-2].close
                curr_c = candles[-1].close
                change = ((curr_c - prev_c) / prev_c) * 100.0 if prev_c > 0 else 0.0
                tickers.append(TickerItem(
                    symbol=sym,
                    price=round(curr_c, prec),
                    change_pct=round(change, 2),
                    is_up=curr_c >= prev_c,
                    precision=prec
                ))
            elif len(candles) == 1:
                curr_c = candles[0].close
                tickers.append(TickerItem(
                    symbol=sym,
                    price=round(curr_c, prec),
                    change_pct=0.0,
                    is_up=True,
                    precision=prec
                ))
        except Exception:
            continue
    return tickers


@router.get("", response_model=List[MarketResponse])
async def list_markets(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Market).where(Market.is_active == True))
    markets = res.scalars().all()
    if not markets:
        # Return standard default market types if DB not seeded yet
        return [
            MarketResponse(id="digital_options", name="Digital Options Style", description="Fixed-time duration research", market_type="DIGITAL_OPTIONS_STYLE", is_active=True, features={"supports_expiry": True}),
            MarketResponse(id="crypto", name="Cryptocurrency", description="24/7 Spot & Futures crypto assets", market_type="CRYPTO", is_active=True, features={"supports_sl_tp": True}),
            MarketResponse(id="forex", name="Forex Currencies", description="Global currency pairs", market_type="FOREX", is_active=True, features={"supports_sl_tp": True}),
            MarketResponse(id="stocks", name="Stocks & Equities", description="US & Global equity markets", market_type="STOCKS", is_active=True, features={"supports_sl_tp": True}),
        ]
    return markets


@router.get("/{market_id}/assets", response_model=List[AssetResponse])
async def list_market_assets(market_id: str, db: AsyncSession = Depends(get_db)):
    provider = market_data_manager.get_provider()
    raw_assets = await provider.get_assets(market_id)
    
    results = []
    for a in raw_assets:
        sym = a["symbol"]
        parts = sym.split("/") if "/" in sym else [sym, "USD"]
        results.append(AssetResponse(
            id=f"{market_id}:{sym}",
            symbol=sym,
            base_asset=parts[0],
            quote_asset=parts[1] if len(parts) > 1 else "USD",
            name=a.get("name", sym),
            market_id=market_id,
            data_source_id=provider.get_provider_name(),
            is_active=True,
            price_precision=a.get("precision", 5),
            min_movement=a.get("min_movement", 0.00001)
        ))
    return results


@router.get("/candles", response_model=List[CandleSchema])
async def get_market_candles(
    symbol: str = Query(..., description="Asset symbol, e.g. EUR/USD or BTC/USDT"),
    timeframe: str = Query("1M", description="Timeframe e.g. 1M, 5M, 15M, 1H"),
    limit: int = Query(100, ge=10, le=1000)
):
    provider = market_data_manager.get_provider()
    candles = await provider.get_candles(symbol, timeframe=timeframe, limit=limit)
    return [CandleSchema.model_validate(c.model_dump()) for c in candles]


@router.get("/data-sources", response_model=List[DataSourceResponse])
async def list_data_sources():
    return [
        DataSourceResponse(id="quotex", name="Quotex OTC Live / Engine", provider_type="live", is_active=True, is_live=True, is_free=True, supported_markets=["digital_options", "forex", "crypto"], rate_limit_per_minute=2000),
        DataSourceResponse(id="binance", name="Binance Public API", provider_type="live", is_active=True, is_live=True, is_free=True, supported_markets=["crypto"], rate_limit_per_minute=1200),
    ]
