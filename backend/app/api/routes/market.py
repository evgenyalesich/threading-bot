from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.api.deps import get_db_session
from app.core.settings import Settings
from app.repositories.candle_repository import CandleRepository
from app.repositories.symbol_mapping_repository import SymbolMappingRepository
from app.schemas.candle_read import CandleRead
from app.schemas.market_pair_read import MarketPairRead
from app.schemas.market_sync_request import MarketSyncRequest
from app.services.binance_candle_service import BinanceCandleService
from app.services.binance_market_service import BinanceMarketService
from app.services.chart_pattern_service import ChartPatternService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.indicator_series_service import IndicatorSeriesService
from app.services.indicator_service import IndicatorService
from app.services.market_data_service import MarketDataService
from app.services.pattern_service import PatternService
from app.services.support_resistance_service import SupportResistanceService
from app.services.symbol_resolver_service import SymbolResolverService


router = APIRouter()
settings = Settings()


@router.post("/sync")
async def sync_market(
    payload: MarketSyncRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    candle_repo = CandleRepository(session)
    market = payload.market.lower()
    data_env = payload.data_env.lower()
    effective_settings = settings.model_copy(update={"binance_testnet": data_env == "testnet"})
    binance_symbol = payload.binance_symbol
    if not binance_symbol:
        mapping_repo = SymbolMappingRepository(session)
        resolver = SymbolResolverService(mapping_repo)
        binance_symbol = await resolver.resolve(payload.symbol.upper(), market)
    service = MarketDataService(candle_repo, BinanceCandleService(effective_settings))
    symbol = payload.symbol.upper()
    inserted = await service.sync_history(
        symbol,
        payload.timeframe,
        payload.lookback_days,
        market=market,
        binance_symbol=binance_symbol,
    )
    return {"inserted": inserted, "source": "binance", "data_env": data_env}


@router.get("/candles")
async def list_candles(
    symbol: str,
    timeframe: str,
    limit: int = 200,
    before: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[CandleRead]:
    candle_repo = CandleRepository(session)
    if before is None:
        candles = await candle_repo.latest(symbol.upper(), timeframe, limit)
    else:
        candles = await candle_repo.before(symbol.upper(), timeframe, before, limit)
    return [CandleRead.model_validate(candle) for candle in candles]


@router.get("/pairs")
async def list_pairs(
    market: str = Query(default="spot"),
    quote: str | None = Query(default=None),
    min_volatility: float | None = Query(default=None),
    data_env: str = Query(default="real"),
) -> list[MarketPairRead]:
    effective_settings = settings.model_copy(update={"binance_testnet": data_env.lower() == "testnet"})
    service = BinanceMarketService(effective_settings)

    try:
        pairs = await service.list_pairs(market)
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="binance_timeout")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="binance_unreachable")

    if quote:
        quote_upper = quote.upper()
        pairs = [pair for pair in pairs if pair.get("quote_asset") == quote_upper]

    if min_volatility is not None:
        pairs = [pair for pair in pairs if pair.get("volatility_score", 0) >= min_volatility]

    return [MarketPairRead.model_validate(pair) for pair in pairs]


@router.get("/indicators")
async def get_indicators(
    symbol: str,
    timeframe: str,
    limit: int = 240,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    candle_repo = CandleRepository(session)
    candles = await candle_repo.latest(symbol.upper(), timeframe, limit)
    service = IndicatorSeriesService(
        indicator_service=IndicatorService(),
        pattern_service=PatternService(),
        support_resistance_service=SupportResistanceService(),
        elliott_wave_service=ElliottWaveService(),
        chart_pattern_service=ChartPatternService(),
    )
    return service.build(candles)
