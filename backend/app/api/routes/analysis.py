from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.settings import Settings
from app.repositories.candle_repository import CandleRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.symbol_mapping_repository import SymbolMappingRepository
from app.schemas.analysis_explain_request import AnalysisExplainRequest
from app.schemas.analysis_explain_response import AnalysisExplainResponse
from app.schemas.analysis_request import AnalysisRequest
from app.schemas.analysis_response import AnalysisResponse
from app.schemas.backtest_progress import BacktestProgressRead
from app.schemas.backtest_request import BacktestRequest
from app.schemas.backtest_response import BacktestResponse, BacktestStatsRead, BacktestTradeRead
from app.schemas.backfill_request import BackfillRequest
from app.schemas.backfill_response import BackfillResponse
from app.schemas.order_read import OrderRead
from app.schemas.scan_request import ScanRequest
from app.schemas.scan_response import ScanDiagnosticsRead, ScanResponse, ScanSignalItem
from app.schemas.signal_read import SignalRead
from app.services.binance_candle_service import BinanceCandleService
from app.services.binance_market_service import BinanceMarketService
from app.services.market_data_service import MarketDataService
from app.services.backtest_service import BacktestService
from app.services.backtest_runtime import get_backtest_runtime
from app.services.market_scan_service import MarketScanService
from app.services.indicator_service import IndicatorService
from app.services.signal_service import SignalService
from app.services.symbol_resolver_service import SymbolResolverService
from app.services.signal_backfill_service import SignalBackfillService
from app.services.pattern_service import PatternService
from app.services.chart_pattern_service import ChartPatternService
from app.services.divergence_service import DivergenceService
from app.services.support_resistance_service import SupportResistanceService
from app.services.fibonacci_service import FibonacciService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.trade_plan_service import TradePlanService
from app.services.signal_execution_service import SignalExecutionConfig, SignalExecutionService
from app.services.telegram_service import TelegramService
from app.strategies.adaptive_pattern_confluence_strategy import AdaptivePatternConfluenceStrategy
from app.strategies.base_strategy import BaseStrategy
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
        min_trend_strength=float(getattr(payload, "min_trend_strength", defaults.min_trend_strength)),
        min_reward_risk=float(getattr(payload, "min_reward_risk", defaults.min_reward_risk)),
        allow_candidate_patterns=bool(getattr(payload, "allow_candidate_patterns", defaults.allow_candidate_patterns)),
        quality_mode=str(getattr(payload, "quality_mode", defaults.quality_mode)),
    )


def _build_adaptive_pattern_confluence_strategy(filters: StrategyFilters) -> AdaptivePatternConfluenceStrategy:
    return AdaptivePatternConfluenceStrategy(
        indicator_service=IndicatorService(),
        pattern_service=PatternService(),
        chart_pattern_service=ChartPatternService(),
        divergence_service=DivergenceService(),
        support_resistance_service=SupportResistanceService(),
        fibonacci_service=FibonacciService(),
        elliott_wave_service=ElliottWaveService(),
        trade_plan_service=TradePlanService(),
        filters=filters,
    )


def _build_strategy_from_payload(payload) -> BaseStrategy:
    filters = _strategy_filters_from_payload(payload)
    # Keep legacy strategy names as aliases, but route everything through the single
    # main production strategy so the app stays focused and predictable.
    return _build_adaptive_pattern_confluence_strategy(filters)


@router.get("/backtest-status")
async def get_backtest_status() -> BacktestProgressRead:
    return get_backtest_runtime().snapshot()


@router.post("/run")
async def run_analysis(
    payload: AnalysisRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
    symbol = payload.symbol.upper()
    candle_repo = CandleRepository(session)
    signal_repo = SignalRepository(session)

    strategy = _build_strategy_from_payload(payload)
    signal_service = SignalService(candle_repo, signal_repo, strategy)

    lookback = payload.lookback_days * _candles_per_day(payload.timeframe)
    signal = await signal_service.run(symbol, payload.timeframe, lookback=lookback)
    if signal is None:
        return AnalysisResponse(status="no_signal")

    signal_read = SignalRead.model_validate(signal)
    try:
        await TelegramService(settings).send_message(
            f"Signal {signal.signal_type.upper()} {signal.symbol} {signal.timeframe}\n"
            f"Entry: {signal.entry_price}\nSL: {signal.stop_loss}\nTP: {signal.take_profit}\n"
            f"Conf: {round(float(signal.confidence or 0) * 100)}%"
        )
    except Exception:
        pass
    if not payload.auto_execute:
        return AnalysisResponse(status="signal", signal=signal_read)

    result = await SignalExecutionService(settings).execute(
        session,
        signal,
        SignalExecutionConfig(
            symbol=symbol,
            timeframe=payload.timeframe,
            market=payload.market,
            trade_env=payload.trade_env,
            order_type=payload.order_type,
            quantity=payload.quantity,
            quote_amount=payload.quote_amount,
            auto_quantity=payload.auto_quantity,
            attach_orders=payload.attach_orders,
            auto_breakeven=payload.auto_breakeven,
            leverage=payload.leverage,
        ),
    )
    if result.order is None:
        return AnalysisResponse(status=result.status, signal=signal_read, error=result.error)
    return AnalysisResponse(status=result.status, signal=signal_read, order=OrderRead.model_validate(result.order))


@router.post("/backfill")
async def backfill_signals(
    payload: BackfillRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BackfillResponse:
    candle_repo = CandleRepository(session)
    signal_repo = SignalRepository(session)

    strategy = _build_strategy_from_payload(payload)
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

    strategy = _build_strategy_from_payload(payload)

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
    results, scan_stats = await scan_service.scan(
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
        only_new_signals_minutes=max(int(payload.only_new_signals_minutes or 0), 0),
        symbol=payload.symbol.upper() if payload.symbol else None,
        market_wide=payload.market_wide,
    )

    response_items = [
        ScanSignalItem(
            symbol=item.symbol,
            binance_symbol=item.binance_symbol,
            chart_symbol=item.chart_symbol,
            chart_url=item.chart_url,
            timeframe=item.timeframe,
            confidence=item.confidence,
            volatility_score=item.volatility_score,
            rank=item.rank,
            signal=SignalRead.model_validate(item.signal),
        )
        for item in results
    ]

    new_signals_count = sum(1 for item in results if getattr(item, "is_new", False))
    return ScanResponse(
        status="ok",
        mode=scan_stats.mode,
        selected_symbol=scan_stats.selected_symbol,
        processed_pairs=scan_stats.processed_pairs,
        universe_pairs=scan_stats.universe_pairs,
        scanned=len(results),
        new_signals_count=new_signals_count,
        has_new_signals=new_signals_count > 0,
        diagnostics=ScanDiagnosticsRead(
            total_pairs=scan_stats.universe_pairs,
            eligible_pairs=scan_stats.eligible_pairs,
            processed_pairs=scan_stats.processed_pairs,
            matched_signals=scan_stats.matched_signals,
            reason_counts=scan_stats.reason_counts,
        ),
        signals=response_items,
    )


@router.post("/backtest")
async def backtest_strategy(
    payload: BacktestRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BacktestResponse:
    runtime = get_backtest_runtime()
    candle_repo = CandleRepository(session)
    market = payload.market.lower()
    data_env = payload.data_env.lower()
    effective_settings = settings.model_copy(update={"binance_testnet": data_env == "testnet"})
    strategy = _build_strategy_from_payload(payload)

    async def _run_single(symbol_value: str):
        if payload.auto_sync:
            binance_symbol = symbol_value.upper()
            mapping_repo = SymbolMappingRepository(session)
            resolver = SymbolResolverService(mapping_repo)
            resolved = await resolver.resolve(symbol_value.upper(), market)
            if resolved:
                binance_symbol = resolved
            mds = MarketDataService(candle_repo, BinanceCandleService(effective_settings))
            await mds.sync_history(
                symbol_value.upper(),
                payload.timeframe,
                payload.lookback_days,
                market=market,
                binance_symbol=binance_symbol,
            )
            trend_tf = getattr(payload, "trend_timeframe", None) or "4h"
            if trend_tf != payload.timeframe:
                await mds.sync_history(
                    symbol_value.upper(),
                    trend_tf,
                    payload.lookback_days,
                    market=market,
                    binance_symbol=binance_symbol,
                )

        cpd = _candles_per_day(payload.timeframe)
        desired_bars = payload.lookback_days * cpd
        effective_max_bars = max(int(payload.max_bars or 0), int(desired_bars))
        effective_max_bars = min(effective_max_bars, 50_000)
        min_window = getattr(strategy, "min_bars", 30)
        window_bars = max(min_window, min(int(cpd * 10), 1200))
        if effective_max_bars > 2:
            window_bars = min(window_bars, effective_max_bars - 2)
        return await BacktestService(candle_repo, strategy).run(
            symbol_value.upper(),
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

    processed_pairs = 0
    universe_pairs = 1
    selected_symbol = payload.symbol.upper()
    mode = "market_wide" if payload.market_wide else "single_pair"
    runtime.start(mode=mode, total_pairs=1, selected_symbol=selected_symbol)

    try:
        if payload.market_wide:
            market_service = BinanceMarketService(effective_settings)
            pairs = await market_service.list_pairs(market)
            universe_pairs = len(pairs)
            quote_filter = payload.quote.upper()
            filtered = [
                pair for pair in pairs
                if not quote_filter or pair.get("quote_asset") == quote_filter
            ]
            filtered.sort(key=lambda item: float(item.get("volatility_score", 0) or 0), reverse=True)
            filtered = filtered[: max(int(payload.max_pairs or 0), 1)]
            processed_pairs = len(filtered)
            selected_symbol = None
            runtime.start(mode=mode, total_pairs=processed_pairs, selected_symbol=None)
            all_trades = []
            for index, pair in enumerate(filtered, start=1):
                runtime.advance(pair["symbol"], processed_pairs=index - 1, matched_trades=len(all_trades))
                pair_trades, _pair_stats = await _run_single(pair["symbol"])
                all_trades.extend(pair_trades)
                runtime.advance(pair["symbol"], processed_pairs=index, matched_trades=len(all_trades))
            all_trades.sort(key=lambda item: (item.entry_time, item.symbol))
            stats = BacktestService(candle_repo, strategy)._stats(
                all_trades,
                initial_equity=payload.initial_equity,
                risk_per_trade=payload.risk_per_trade,
            )
            trades = all_trades
        else:
            runtime.start(mode=mode, total_pairs=1, selected_symbol=selected_symbol)
            runtime.advance(payload.symbol.upper(), processed_pairs=0, matched_trades=0)
            processed_pairs = 1
            trades, stats = await _run_single(payload.symbol)
            runtime.advance(payload.symbol.upper(), processed_pairs=1, matched_trades=len(trades))
        runtime.finish(processed_pairs=processed_pairs, matched_trades=len(trades))
    except Exception as exc:
        runtime.fail(str(exc))
        raise

    return BacktestResponse(
        status="ok",
        mode=mode,
        selected_symbol=selected_symbol,
        processed_pairs=processed_pairs,
        universe_pairs=universe_pairs,
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
    strategy = _build_strategy_from_payload(payload)
    context: dict | None = None
    if getattr(strategy, "is_mtf", False):
        trend_tf = getattr(strategy, "trend_timeframe", None) or getattr(strategy, "h1_timeframe", "1h")
        trend_candles = await candle_repo.latest(payload.symbol.upper(), trend_tf, limit=300)
        if trend_candles:
            trend_df = candles_to_df(trend_candles)
            context = {
                "trend_data": trend_df,
                "h1_data": trend_df,  # legacy compat
                "timeframe": payload.timeframe,
            }
    elif context is None:
        context = {"timeframe": payload.timeframe}
    debug = strategy.explain(data, context)
    status = "ok" if not debug.get("reasons") else "no_signal"
    return AnalysisExplainResponse(status=status, debug=debug)
