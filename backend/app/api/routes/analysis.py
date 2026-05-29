from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.settings import Settings
from app.repositories.candle_repository import CandleRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.symbol_mapping_repository import SymbolMappingRepository
from app.schemas.analysis_explain_request import AnalysisExplainRequest
from app.schemas.analysis_explain_response import AnalysisExplainResponse
from app.schemas.analysis_request import AnalysisRequest
from app.schemas.analysis_response import AnalysisResponse
from app.schemas.backtest_request import BacktestRequest
from app.schemas.backtest_response import BacktestResponse, BacktestStatsRead, BacktestTradeRead
from app.schemas.backfill_request import BackfillRequest
from app.schemas.backfill_response import BackfillResponse
from app.schemas.order_create import OrderCreate
from app.schemas.order_read import OrderRead
from app.schemas.scan_request import ScanRequest
from app.schemas.scan_response import ScanResponse, ScanSignalItem
from app.schemas.signal_read import SignalRead
from app.exchanges.binance_exchange import BinanceExchange
from app.services.binance_candle_service import BinanceCandleService
from app.services.binance_market_service import BinanceMarketService
from app.services.market_data_service import MarketDataService
from app.services.backtest_service import BacktestService
from app.services.execution_service import ExecutionService
from app.services.market_scan_service import MarketScanService
from app.services.order_sizing_service import OrderSizingService
from app.services.indicator_service import IndicatorService
from app.services.signal_service import SignalService
from app.services.symbol_resolver_service import SymbolResolverService
from app.services.signal_backfill_service import SignalBackfillService
from app.services.binance_credentials import resolve_api_credentials
from app.strategies.three_screens_strategy import ThreeScreensStrategy
from app.strategies.strategy_filters import StrategyFilters
from app.utils.candle_frame import candles_to_df


router = APIRouter()
settings = Settings()


def _candles_per_day(timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == "m":
        return max(int(24 * 60 / value), 1)
    if unit == "h":
        return max(int(24 / value), 1)
    return 1


def _strategy_filters_from_payload(payload) -> StrategyFilters:
    # Payloads share the same filter field names across analysis/scan/backfill/backtest.
    defaults = StrategyFilters()
    return StrategyFilters(
        min_confidence=float(getattr(payload, "min_confidence", defaults.min_confidence)),
        min_confirmations=int(getattr(payload, "min_confirmations", defaults.min_confirmations)),
        require_pattern=bool(getattr(payload, "require_pattern", False)),
        require_divergence=bool(getattr(payload, "require_divergence", False)),
        require_candle=bool(getattr(payload, "require_candle", False)),
        require_volume_confirm=bool(getattr(payload, "require_volume_confirm", False)),
    )


def _build_strategy(
    filters: StrategyFilters,
    h1_timeframe: str = "1h",
    trend_timeframe: str | None = None,
) -> ThreeScreensStrategy:
    return ThreeScreensStrategy(
        indicator_service=IndicatorService(),
        trend_timeframe=trend_timeframe or "4h",
        h1_timeframe=h1_timeframe,
        filters=filters,
    )


@router.post("/run")
async def run_analysis(
    payload: AnalysisRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
    symbol = payload.symbol.upper()
    candle_repo = CandleRepository(session)
    signal_repo = SignalRepository(session)

    strategy = _build_strategy(
        _strategy_filters_from_payload(payload),
        h1_timeframe=getattr(payload, "h1_timeframe", "1h"),
        trend_timeframe=getattr(payload, "trend_timeframe", None),
    )
    signal_service = SignalService(candle_repo, signal_repo, strategy)

    lookback = payload.lookback_days * _candles_per_day(payload.timeframe)
    signal = await signal_service.run(symbol, payload.timeframe, lookback=lookback)
    if signal is None:
        return AnalysisResponse(status="no_signal")

    signal_read = SignalRead.model_validate(signal)
    if not payload.auto_execute:
        return AnalysisResponse(status="signal", signal=signal_read)

    market = payload.market.lower()
    trade_env = payload.trade_env.lower()
    trade_settings = settings.model_copy(update={"binance_testnet": trade_env == "testnet"})
    if market == "spot" and signal.signal_type == "short":
        return AnalysisResponse(status="spot_short_not_supported", signal=signal_read)

    mapping_repo = SymbolMappingRepository(session)
    resolver = SymbolResolverService(mapping_repo)
    resolved_symbol = await resolver.resolve(symbol, market)
    if not resolved_symbol:
        return AnalysisResponse(status="symbol_not_mapped", signal=signal_read)

    quantity = payload.quantity if payload.quantity > 0 else settings.default_order_quantity
    if payload.auto_quantity or payload.quote_amount is not None:
        if payload.quote_amount is None:
            return AnalysisResponse(
                status="order_sizing_error",
                signal=signal_read,
                error="quote_amount_required",
            )
        sizing_service = OrderSizingService(BinanceMarketService(trade_settings))
        sizing = await sizing_service.size_order(
            resolved_symbol,
            market,
            payload.quote_amount,
            signal.entry_price,
        )
        if sizing.error:
            return AnalysisResponse(status="order_sizing_error", signal=signal_read, error=sizing.error)
        quantity = sizing.quantity or quantity

    order_repo = OrderRepository(session)
    exchange = None
    api_key, api_secret, _ = resolve_api_credentials(settings, trade_env, market)
    if api_key and api_secret:
        exchange = BinanceExchange(trade_settings)
    execution_service = ExecutionService(order_repo, exchange)
    trade_plan = signal.meta.get("trade_plan") if signal.meta else None
    order_create = OrderCreate(
        exchange="binance",
        market=market,
        symbol=resolved_symbol,
        side="BUY" if signal.signal_type == "long" else "SELL",
        order_type=payload.order_type,
        quantity=quantity,
        trade_env=payload.trade_env,
        quote_amount=payload.quote_amount,
        auto_quantity=payload.auto_quantity,
        timeframe=payload.timeframe,
        signal_id=signal.id,
        price=signal.entry_price,
        leverage=payload.leverage,
        stop_loss=(trade_plan.get("stop_loss") if trade_plan else signal.stop_loss),
        take_profit=(trade_plan.get("take_profit") if trade_plan else signal.take_profit),
        take_levels=(trade_plan.get("take_levels") if trade_plan else None),
        breakeven_at=(trade_plan.get("breakeven_at") if trade_plan else None),
        auto_breakeven=payload.auto_breakeven,
        attach_orders=payload.attach_orders,
    )
    order = await execution_service.place_order(order_create, market=market)
    status = "order_submitted" if order.status == "submitted" else "order_stored"
    return AnalysisResponse(status=status, signal=signal_read, order=OrderRead.model_validate(order))


@router.post("/backfill")
async def backfill_signals(
    payload: BackfillRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BackfillResponse:
    candle_repo = CandleRepository(session)
    signal_repo = SignalRepository(session)

    strategy = _build_strategy(
        _strategy_filters_from_payload(payload),
        h1_timeframe=getattr(payload, "h1_timeframe", "1h"),
        trend_timeframe=getattr(payload, "trend_timeframe", None),
    )
    backfill_service = SignalBackfillService(candle_repo, signal_repo, strategy)

    lookback = payload.lookback_days * _candles_per_day(payload.timeframe)
    inserted = await backfill_service.backfill(
        payload.symbol.upper(),
        payload.timeframe,
        lookback=lookback,
        stride=payload.stride,
        max_bars=payload.max_bars,
    )
    return BackfillResponse(status="ok", inserted=inserted)


@router.post("/scan")
async def scan_market(
    payload: ScanRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ScanResponse:
    candle_repo = CandleRepository(session)
    signal_repo = SignalRepository(session)

    strategy = _build_strategy(
        _strategy_filters_from_payload(payload),
        h1_timeframe=getattr(payload, "h1_timeframe", "1h"),
        trend_timeframe=getattr(payload, "trend_timeframe", None),
    )

    data_env = payload.data_env.lower()
    effective_settings = settings.model_copy(update={"binance_testnet": data_env == "testnet"})
    market_service = BinanceMarketService(effective_settings)
    scan_service = MarketScanService(
        candle_repo,
        signal_repo,
        market_service,
        strategy,
        BinanceCandleService(effective_settings),
    )

    lookback = payload.lookback_days * _candles_per_day(payload.timeframe)
    results = await scan_service.scan(
        market=payload.market.lower(),
        timeframe=payload.timeframe,
        lookback=lookback,
        lookback_days=payload.lookback_days,
        quote=payload.quote.upper(),
        min_volatility=payload.min_volatility,
        max_pairs=payload.max_pairs,
        limit=payload.limit,
        auto_sync=payload.auto_sync,
        store_signals=payload.store_signals,
    )

    response_items = [
        ScanSignalItem(
            symbol=item.symbol,
            binance_symbol=item.binance_symbol,
            timeframe=item.timeframe,
            confidence=item.confidence,
            volatility_score=item.volatility_score,
            rank=item.rank,
            signal=SignalRead.model_validate(item.signal),
        )
        for item in results
    ]

    return ScanResponse(status="ok", scanned=len(results), signals=response_items)


@router.post("/backtest")
async def backtest_strategy(
    payload: BacktestRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BacktestResponse:
    candle_repo = CandleRepository(session)
    market = payload.market.lower()
    data_env = payload.data_env.lower()
    effective_settings = settings.model_copy(update={"binance_testnet": data_env == "testnet"})

    if payload.auto_sync:
        binance_symbol = payload.symbol.upper()
        mapping_repo = SymbolMappingRepository(session)
        resolver = SymbolResolverService(mapping_repo)
        resolved = await resolver.resolve(payload.symbol.upper(), market)
        if resolved:
            binance_symbol = resolved
        mds = MarketDataService(candle_repo, BinanceCandleService(effective_settings))
        await mds.sync_history(
            payload.symbol.upper(),
            payload.timeframe,
            payload.lookback_days,
            market=market,
            binance_symbol=binance_symbol,
        )
        # Also sync trend timeframe for MTF strategies
        trend_tf = getattr(payload, "trend_timeframe", None) or "4h"
        if trend_tf != payload.timeframe:
            await mds.sync_history(
                payload.symbol.upper(),
                trend_tf,
                payload.lookback_days,
                market=market,
                binance_symbol=binance_symbol,
            )

    strategy = _build_strategy(
        _strategy_filters_from_payload(payload),
        h1_timeframe=getattr(payload, "h1_timeframe", "1h"),
        trend_timeframe=getattr(payload, "trend_timeframe", None),
    )

    cpd = _candles_per_day(payload.timeframe)
    desired_bars = payload.lookback_days * cpd
    # Protect local runs from accidentally requesting hundreds of thousands of 1m candles.
    effective_max_bars = max(int(payload.max_bars or 0), int(desired_bars))
    effective_max_bars = min(effective_max_bars, 50_000)
    # Strategy window: enough for Three Screens + some context.
    min_window = getattr(strategy, "min_bars", 30)
    window_bars = max(min_window, min(int(cpd * 10), 1200))
    if effective_max_bars > 2:
        window_bars = min(window_bars, effective_max_bars - 2)
    trades, stats = await BacktestService(candle_repo, strategy).run(
        payload.symbol.upper(),
        payload.timeframe,
        window_bars=window_bars,
        max_bars=effective_max_bars,
        stride=payload.stride,
        initial_equity=payload.initial_equity,
        risk_per_trade=payload.risk_per_trade,
        fee_bps=payload.fee_bps,
        slippage_bps=payload.slippage_bps,
        intra_candle_mode=(payload.intra_candle_mode or "pessimistic").lower(),
    )

    return BacktestResponse(
        status="ok",
        trades=[BacktestTradeRead.model_validate(trade) for trade in trades],
        stats=BacktestStatsRead.model_validate(stats),
    )


@router.post("/explain")
async def explain_analysis(
    payload: AnalysisExplainRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisExplainResponse:
    candle_repo = CandleRepository(session)
    lookback = payload.lookback_days * _candles_per_day(payload.timeframe)
    candles = await candle_repo.latest(payload.symbol.upper(), payload.timeframe, limit=lookback)
    if not candles:
        return AnalysisExplainResponse(status="no_data", debug={"reasons": ["no_candles_in_db"]})

    data = candles_to_df(candles)
    strategy = _build_strategy(
        _strategy_filters_from_payload(payload),
        h1_timeframe=getattr(payload, "h1_timeframe", "1h"),
        trend_timeframe=getattr(payload, "trend_timeframe", None),
    )
    context: dict | None = None
    if getattr(strategy, "is_mtf", False):
        trend_tf = getattr(strategy, "trend_timeframe", None) or getattr(strategy, "h1_timeframe", "1h")
        trend_candles = await candle_repo.latest(payload.symbol.upper(), trend_tf, limit=300)
        if trend_candles:
            trend_df = candles_to_df(trend_candles)
            context = {
                "trend_data": trend_df,
                "h1_data": trend_df,  # legacy compat
            }
    debug = strategy.explain(data, context)
    status = "ok" if not debug.get("reasons") else "no_signal"
    return AnalysisExplainResponse(status=status, debug=debug)
