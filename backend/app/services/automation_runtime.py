from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session_manager
from app.core.settings import Settings
from app.models.order import Order
from app.models.signal import Signal
from app.repositories.candle_repository import CandleRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.signal_repository import SignalRepository
from app.schemas.automation import AutomationStateRead
from app.schemas.order_read import OrderRead
from app.schemas.signal_read import SignalRead
from app.services.binance_candle_service import BinanceCandleService
from app.services.binance_market_service import BinanceMarketService
from app.services.chart_pattern_service import ChartPatternService
from app.services.divergence_service import DivergenceService
from app.services.elliott_wave_service import ElliottWaveService
from app.services.fibonacci_service import FibonacciService
from app.services.indicator_service import IndicatorService
from app.services.market_data_service import MarketDataService
from app.services.market_scan_service import MarketScanService, ScanRunStats
from app.services.order_sync_service import OrderSyncService
from app.services.pattern_service import PatternService
from app.services.signal_execution_service import (
    SignalExecutionConfig,
    SignalExecutionService,
)
from app.services.support_resistance_service import SupportResistanceService
from app.services.telegram_service import TelegramService
from app.services.trade_plan_service import TradePlanService
from app.strategies.adaptive_pattern_confluence_strategy import AdaptivePatternConfluenceStrategy
from app.strategies.strategy_filters import StrategyFilters
from app.utils.candle_frame import candles_to_df
from app.utils.jsonable import to_jsonable


def _candles_per_day(timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == "m":
        return max(int(24 * 60 / value), 1)
    if unit == "h":
        return max(int(24 / value), 1)
    return 1


def _normalize_mode(value: str | None) -> str:
    return "auto" if str(value or "").strip().lower() == "auto" else "semi"


@dataclass(slots=True)
class AutomationConfig:
    enabled: bool = False
    mode: str = "semi"
    symbol: str = "BTCUSDT"
    scan_market_wide: bool = True
    quote: str = ""
    max_pairs: int = 631
    timeframe: str = "1h"
    market: str = "futures"
    data_env: str = "testnet"
    trade_env: str = "testnet"
    lookback_days: int = 120
    quantity: float = 0.001
    quote_amount: float | None = 0.5
    auto_quantity: bool = True
    attach_orders: bool = True
    auto_breakeven: bool = True
    leverage: int | None = 25
    min_confidence: float = 0.35
    min_confirmations: int = 1
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
    min_trend_strength: float = 0.12
    min_reward_risk: float = 2.2
    allow_candidate_patterns: bool = True
    quality_mode: str = "balanced"
    h1_timeframe: str = "1h"
    trend_timeframe: str = "4h"
    poll_interval_sec: int = 45


@dataclass(slots=True)
class PendingApproval:
    signal_id: int
    signal: Signal
    created_at: datetime


@dataclass(slots=True)
class AutomationLog:
    id: str
    level: str
    event: str
    message: str
    created_at: datetime
    meta: dict | None = None


@dataclass(slots=True)
class TelegramSession:
    status_message_id: int | None = None
    view: str = "home"
    awaiting_input: str | None = None
    target_id: int | None = None


class AutomationRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session_manager = get_session_manager()
        self._telegram = TelegramService(settings)
        self._executor = SignalExecutionService(settings)
        self._config = AutomationConfig(enabled=settings.automation_enabled_on_start)
        self._pending: list[PendingApproval] = []
        self._logs: list[AutomationLog] = []
        self._latest_signal: Signal | None = None
        self._latest_order: Order | None = None
        self._last_signal_fingerprint: str | None = None
        self._live_state: str = "idle" if self._config.enabled else "off"
        self._live_message: str | None = (
            "Ожидание первого цикла." if self._config.enabled else "Автоматизация остановлена."
        )
        self._last_check_at: datetime | None = None
        self._last_signal_at: datetime | None = None
        self._last_error: str | None = None
        self._last_no_signal_reason: str | None = None
        self._last_update_received_at: datetime | None = None
        self._last_callback_handled_at: datetime | None = None
        self._last_telegram_error: str | None = None
        self._last_scan_stats: ScanRunStats | None = None
        self._scan_processed_pairs = 0
        self._scan_total_pairs = 0
        self._scan_matched_signals = 0
        self._scan_phase: str | None = None
        self._next_check_at: datetime | None = None
        self._last_progress_push_at: datetime | None = None
        self._worker_task: asyncio.Task | None = None
        self._command_task: asyncio.Task | None = None
        self._updates_offset = 0
        self._processed_callbacks: set[str] = set()
        self._telegram_sessions: dict[str, TelegramSession] = {}
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop(), name="automation-worker")
        if self._telegram.enabled() and (self._command_task is None or self._command_task.done()):
            self._command_task = asyncio.create_task(self._telegram_loop(), name="telegram-command-worker")

    async def shutdown(self) -> None:
        for task in (self._worker_task, self._command_task):
            if task and not task.done():
                task.cancel()
        for task in (self._worker_task, self._command_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def update_config(self, **changes) -> None:
        allowed = set(asdict(self._config).keys())
        for key, value in changes.items():
            if key not in allowed or value is None:
                continue
            if key == "mode":
                value = _normalize_mode(value)
            if key in {"symbol"}:
                value = str(value).upper().replace("-", "")
            if key in {"timeframe", "market", "data_env", "trade_env", "h1_timeframe", "trend_timeframe", "quality_mode"}:
                value = str(value).lower()
            if key == "quote":
                value = str(value).upper()
            if key == "lookback_days":
                value = max(int(value), 10)
            if key == "max_pairs":
                value = min(max(int(value), 1), 631)
            if key == "poll_interval_sec":
                value = min(max(int(value), 15), 900)
            setattr(self._config, key, value)
        if {"market", "scan_market_wide", "symbol", "timeframe", "max_pairs"} & set(changes):
            self._last_scan_stats = None
        if "enabled" in changes:
            self._config.enabled = bool(changes["enabled"])
        self._add_log("info", "config_updated", "Automation config updated.", meta=self._config_snapshot_meta())

    def set_mode(self, mode: str) -> None:
        self._config.mode = _normalize_mode(mode)
        self._add_log("info", "mode_changed", f"Mode switched to {self._config.mode}.", meta={"mode": self._config.mode})

    def set_trade_env(self, trade_env: str) -> None:
        self._config.trade_env = str(trade_env).lower()
        self._add_log("info", "trade_env_changed", f"Trade env set to {self._config.trade_env}.", meta={"trade_env": self._config.trade_env})

    def set_enabled(self, enabled: bool) -> None:
        self._config.enabled = bool(enabled)
        self._live_state = "idle" if enabled else "off"
        self._live_message = "Ожидание следующего цикла." if enabled else "Автоматизация остановлена."
        self._add_log("info", "automation_toggled", "Automation started." if enabled else "Automation stopped.", meta={"enabled": enabled})

    async def run_cycle_now(self) -> None:
        await self._process_cycle(force=True)

    async def _run_cycle_safe(self) -> None:
        try:
            await self.run_cycle_now()
        except Exception as exc:
            self._last_error = str(exc)
            self._live_state = "error"
            self._live_message = f"Ошибка сканирования: {str(exc)[:200]}"
            self._add_log("error", "manual_scan_error", str(exc)[:500])

    async def approve(self, signal_id: int) -> Order | None:
        async with self._lock:
            pending = next((item for item in self._pending if item.signal_id == signal_id), None)
            if not pending:
                return None
            order = await self._execute_signal(pending.signal)
            self._pending = [item for item in self._pending if item.signal_id != signal_id]
            return order

    def reject(self, signal_id: int) -> bool:
        before = len(self._pending)
        self._pending = [item for item in self._pending if item.signal_id != signal_id]
        removed = len(self._pending) != before
        if removed:
            self._add_log("info", "approval_rejected", f"Signal {signal_id} rejected.", meta={"signal_id": signal_id})
        return removed

    async def snapshot(self) -> AutomationStateRead:
        latest_order = self._latest_order
        recent_orders: list[OrderRead] = []
        recent_signals: list[SignalRead] = []
        try:
            if latest_order is not None and self._live_state != "scanning":
                async with self._session_manager.session_factory()() as session:
                    latest_order = await OrderSyncService(OrderRepository(session), self._settings).sync_one(latest_order)
                    self._latest_order = latest_order
            async with self._session_manager.session_factory()() as session:
                order_repo = OrderRepository(session)
                signal_repo = SignalRepository(session)
                recent_orders = [OrderRead.model_validate(order) for order in await order_repo.list_recent(limit=8)]
                recent_signals = [SignalRead.model_validate(signal) for signal in await signal_repo.list_recent(limit=8)]
        except Exception as exc:
            self._last_error = f"snapshot_history_unavailable: {str(exc)[:220]}"
        return AutomationStateRead(
            enabled=self._config.enabled,
            worker_running=bool(self._worker_task and not self._worker_task.done()),
            telegram_enabled=self._telegram.enabled(),
            telegram_worker_running=bool(self._command_task and not self._command_task.done()),
            live_state=self._live_state,
            live_message=self._live_message,
            mode=self._config.mode,
            symbol=self._config.symbol,
            scan_market_wide=self._config.scan_market_wide,
            quote=self._config.quote,
            max_pairs=self._config.max_pairs,
            timeframe=self._config.timeframe,
            market=self._config.market,
            data_env=self._config.data_env,
            trade_env=self._config.trade_env,
            lookback_days=self._config.lookback_days,
            quantity=self._config.quantity,
            quote_amount=self._config.quote_amount,
            auto_quantity=self._config.auto_quantity,
            attach_orders=self._config.attach_orders,
            auto_breakeven=self._config.auto_breakeven,
            leverage=self._config.leverage,
            min_confidence=self._config.min_confidence,
            min_confirmations=self._config.min_confirmations,
            require_pattern=self._config.require_pattern,
            require_divergence=self._config.require_divergence,
            require_candle=self._config.require_candle,
            require_volume_confirm=self._config.require_volume_confirm,
            min_trend_strength=self._config.min_trend_strength,
            min_reward_risk=self._config.min_reward_risk,
            allow_candidate_patterns=self._config.allow_candidate_patterns,
            quality_mode=self._config.quality_mode,
            h1_timeframe=self._config.h1_timeframe,
            trend_timeframe=self._config.trend_timeframe,
            poll_interval_sec=self._config.poll_interval_sec,
            scan_processed_pairs=self._scan_processed_pairs,
            scan_total_pairs=self._scan_total_pairs,
            scan_matched_signals=self._scan_matched_signals,
            scan_phase=self._scan_phase,
            next_check_at=self._next_check_at,
            last_check_at=self._last_check_at,
            last_signal_at=self._last_signal_at,
            last_error=self._last_error,
            last_no_signal_reason=self._last_no_signal_reason,
            last_update_received_at=self._last_update_received_at,
            last_callback_handled_at=self._last_callback_handled_at,
            last_telegram_error=self._last_telegram_error,
            pending_approvals=[
                {
                    "signal_id": item.signal_id,
                    "symbol": item.signal.symbol,
                    "timeframe": item.signal.timeframe,
                    "signal_type": item.signal.signal_type,
                    "confidence": item.signal.confidence,
                    "entry_price": item.signal.entry_price,
                    "stop_loss": item.signal.stop_loss,
                    "take_profit": item.signal.take_profit,
                    "rationale": item.signal.rationale,
                    "created_at": item.created_at,
                }
                for item in self._pending
            ],
            logs=[
                {
                    "id": log.id,
                    "level": log.level,
                    "event": log.event,
                    "message": log.message,
                    "created_at": log.created_at,
                    "meta": log.meta,
                }
                for log in self._logs
            ],
            latest_signal=SignalRead.model_validate(self._latest_signal) if self._latest_signal else None,
            latest_order=OrderRead.model_validate(latest_order) if latest_order else None,
            recent_signals=recent_signals,
            recent_orders=recent_orders,
        )

    async def _worker_loop(self) -> None:
        while True:
            try:
                await self._process_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)
                self._add_log("error", "automation_worker_error", str(exc)[:500])
            self._next_check_at = datetime.now(UTC) + timedelta(seconds=self._config.poll_interval_sec)
            await asyncio.sleep(self._config.poll_interval_sec)

    async def _process_cycle(self, force: bool = False) -> None:
        if not self._config.enabled and not force:
            return
        async with self._lock:
            self._last_check_at = datetime.now(UTC)
            self._next_check_at = None
            self._scan_processed_pairs = 0
            self._scan_total_pairs = 0
            self._scan_matched_signals = 0
            self._scan_phase = "starting"
            self._live_state = "scanning"
            self._live_message = "Ищем свежий сетап по выбранному рынку."
            async with self._session_manager.session_factory()() as session:
                signal = await self._detect_signal(session)
                if signal is None:
                    self._live_state = "idle"
                    self._live_message = (
                        f"Сигналов нет. Основная причина: {self._last_no_signal_reason}"
                        if self._last_no_signal_reason
                        else "В этом цикле подходящих сигналов нет."
                    )
                    self._scan_phase = "complete"
                    self._next_check_at = datetime.now(UTC) + timedelta(seconds=self._config.poll_interval_sec)
                    asyncio.create_task(self._push_progress_cards(), name="telegram-scan-complete")
                    return
                self._latest_signal = signal
                self._last_signal_at = datetime.now(UTC)
                self._live_state = "signal_found"
                self._live_message = f"Найден сигнал: {signal.signal_type.upper()} {signal.symbol} {signal.timeframe}"
                self._add_log(
                    "info",
                    "signal_detected",
                    f"{signal.signal_type.upper()} {signal.symbol} {signal.timeframe}",
                    meta={"signal_id": signal.id, "confidence": signal.confidence},
                )
                signal_markup = (
                    self._telegram.signal_actions_keyboard(signal.id)
                    if self._config.mode == "semi"
                    else self._telegram.default_keyboard()
                )
                await self._telegram.send_message(
                    self._format_signal_message(signal, auto=self._config.mode == "auto"),
                    reply_markup=signal_markup,
                )
                if self._config.mode == "auto":
                    self._live_state = "executing"
                    self._live_message = f"Открываем сделку по {signal.symbol}."
                    await self._execute_signal(signal)
                else:
                    self._pending = [item for item in self._pending if item.signal_id != signal.id]
                    self._pending.insert(0, PendingApproval(signal_id=signal.id, signal=signal, created_at=datetime.now(UTC)))
                    self._pending = self._pending[:20]
                    self._live_state = "waiting_approve"
                    self._live_message = f"Сигнал #{signal.id} ждет твоего решения."
                self._scan_phase = "complete"
                self._next_check_at = datetime.now(UTC) + timedelta(seconds=self._config.poll_interval_sec)
                asyncio.create_task(self._push_progress_cards(), name="telegram-scan-complete")

    def _update_scan_progress(self, processed: int, total: int, matched: int, phase: str) -> None:
        self._scan_processed_pairs = processed
        self._scan_total_pairs = total
        self._scan_matched_signals = matched
        self._scan_phase = phase
        phase_label = "Загрузка истории" if phase == "history" else "Анализ стратегии"
        suffix = "пока найдено" if phase == "analysis" else "найдено ранее"
        self._live_message = f"{phase_label}: обработано {processed}/{total}, {suffix} сигналов {matched}."
        now = datetime.now(UTC)
        if (
            processed == total
            or self._last_progress_push_at is None
            or (now - self._last_progress_push_at).total_seconds() >= 3
        ):
            self._last_progress_push_at = now
            asyncio.create_task(self._push_progress_cards(), name="telegram-scan-progress")

    async def _push_progress_cards(self) -> None:
        for chat_id, telegram_session in list(self._telegram_sessions.items()):
            if telegram_session.status_message_id is None or telegram_session.view not in {"home", "live"}:
                continue
            try:
                await self._render_telegram_view(
                    chat_id,
                    telegram_session.view,
                    message_id=telegram_session.status_message_id,
                )
            except Exception as exc:
                self._last_telegram_error = str(exc)

    async def _detect_signal(self, session: AsyncSession) -> Signal | None:
        config = self._config
        self._last_no_signal_reason = None
        effective_settings = self._settings.model_copy(update={"binance_testnet": config.data_env == "testnet"})
        candle_repo = CandleRepository(session)
        signal_repo = SignalRepository(session)

        filters = StrategyFilters(
            min_confidence=config.min_confidence,
            min_confirmations=config.min_confirmations,
            require_pattern=config.require_pattern,
            require_divergence=config.require_divergence,
            require_candle=config.require_candle,
            require_volume_confirm=config.require_volume_confirm,
            min_trend_strength=config.min_trend_strength,
            min_reward_risk=config.min_reward_risk,
            allow_candidate_patterns=config.allow_candidate_patterns,
            quality_mode=config.quality_mode,
        )
        strategy = AdaptivePatternConfluenceStrategy(
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
        strategy.h1_timeframe = config.h1_timeframe
        strategy.trend_timeframe = config.trend_timeframe

        if config.scan_market_wide:
            market_service = BinanceMarketService(effective_settings)
            scan_service = MarketScanService(
                candle_repo,
                signal_repo,
                market_service,
                strategy,
                BinanceCandleService(effective_settings),
            )
            results, scan_stats = await scan_service.scan(
                market=config.market,
                timeframe=config.timeframe,
                lookback=config.lookback_days * _candles_per_day(config.timeframe),
                lookback_days=config.lookback_days,
                quote=config.quote.upper(),
                min_volatility=0.0,
                max_pairs=config.max_pairs,
                limit=1,
                auto_sync=True,
                store_signals=True,
                only_new_signals_minutes=max(config.poll_interval_sec // 3, 15),
                symbol=config.symbol,
                market_wide=config.scan_market_wide,
                progress_callback=self._update_scan_progress,
            )
            self._last_scan_stats = scan_stats
            if not results:
                if scan_stats.reason_counts:
                    top_reason = max(scan_stats.reason_counts.items(), key=lambda item: item[1])[0]
                    self._last_no_signal_reason = top_reason
                else:
                    self._last_no_signal_reason = "no_signal_in_universe"
                return None
            signal = results[0].signal
            fingerprint = self._signal_fingerprint(
                signal.symbol,
                signal.timeframe,
                {
                    "signal_type": signal.signal_type,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                },
            )
            if fingerprint == self._last_signal_fingerprint:
                return None
            self._last_signal_fingerprint = fingerprint
            return signal

        mds = MarketDataService(candle_repo, BinanceCandleService(effective_settings))
        await mds.sync_history(
            config.symbol,
            config.timeframe,
            config.lookback_days,
            market=config.market,
            binance_symbol=config.symbol,
        )
        if config.trend_timeframe != config.timeframe:
            await mds.sync_history(
                config.symbol,
                config.trend_timeframe,
                config.lookback_days,
                market=config.market,
                binance_symbol=config.symbol,
            )

        lookback = config.lookback_days * _candles_per_day(config.timeframe)
        candles = await candle_repo.latest(config.symbol, config.timeframe, limit=lookback)
        if not candles:
            return None
        data = candles_to_df(candles)
        context: dict | None = None
        trend_candles = await candle_repo.latest(config.symbol, config.trend_timeframe, limit=300)
        if trend_candles:
            trend_df = candles_to_df(trend_candles)
            context = {"trend_data": trend_df, "h1_data": trend_df, "timeframe": config.timeframe}
        signal_payload = strategy.evaluate(data, context)
        if not signal_payload:
            debug = strategy.explain(data, context)
            reasons = list(debug.get("reasons") or [])
            self._last_no_signal_reason = reasons[0] if reasons else "no_signal_components"
            return None
        fingerprint = self._signal_fingerprint(config.symbol, config.timeframe, signal_payload)
        if fingerprint == self._last_signal_fingerprint:
            return None
        self._last_signal_fingerprint = fingerprint
        signal = Signal(
            symbol=config.symbol,
            timeframe=config.timeframe,
            signal_type=signal_payload["signal_type"],
            confidence=float(signal_payload["confidence"]),
            entry_price=to_jsonable(signal_payload.get("entry_price")),
            stop_loss=to_jsonable(signal_payload.get("stop_loss")),
            take_profit=to_jsonable(signal_payload.get("take_profit")),
            meta=to_jsonable(signal_payload.get("meta")),
            rationale=signal_payload.get("rationale"),
        )
        return await signal_repo.add(signal)

    async def _execute_signal(self, signal: Signal) -> Order | None:
        async with self._session_manager.session_factory()() as session:
            result = await self._executor.execute(
                session,
                signal,
                SignalExecutionConfig(
                    symbol=signal.symbol,
                    timeframe=signal.timeframe,
                    market=self._config.market,
                    trade_env=self._config.trade_env,
                    quantity=self._config.quantity,
                    quote_amount=self._config.quote_amount,
                    auto_quantity=self._config.auto_quantity,
                    attach_orders=self._config.attach_orders,
                    auto_breakeven=self._config.auto_breakeven,
                    leverage=self._config.leverage,
                ),
            )
            if result.order:
                self._latest_order = result.order
                self._live_state = "order_open"
                self._live_message = f"Позиция открыта: #{result.order.id} {result.order.side} {result.order.symbol}"
                self._add_log(
                    "info",
                    "order_executed",
                    f"{result.order.side} {result.order.symbol} {result.status}",
                    meta={"order_id": result.order.id, "status": result.status},
                )
                await self._telegram.send_message(
                    f"Automation order {result.order.side} {result.order.symbol}\n"
                    f"Status: {result.order.status}\nEntry: {result.order.price}\n"
                    f"SL: {result.order.stop_loss}\nTP: {result.order.take_profit}",
                    reply_markup=self._telegram.order_actions_keyboard(result.order.id),
                )
                return result.order
            self._last_error = result.error
            self._live_state = "error"
            self._live_message = result.error or result.status
            self._add_log("error", "order_execution_failed", result.error or result.status, meta={"status": result.status})
            return None

    def _get_telegram_session(self, chat_id: str) -> TelegramSession:
        session = self._telegram_sessions.get(chat_id)
        if session is None:
            session = TelegramSession()
            self._telegram_sessions[chat_id] = session
        return session

    def _is_authorized_chat(self, chat_id: str) -> bool:
        allowed = self._settings.telegram_allowed_chat_id_list()
        return bool(chat_id) and (not allowed or chat_id in allowed)

    def _risk_profile_label(self) -> str:
        quality = str(self._config.quality_mode or "").lower()
        if quality in {"sniper", "balanced", "aggressive"}:
            return quality
        return "balanced"

    @staticmethod
    def _format_price(value: float | None) -> str:
        if value is None:
            return "--"
        return f"{float(value):.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_time(value: datetime | None) -> str:
        if not value:
            return "--"
        return value.astimezone().strftime("%d.%m %H:%M:%S")

    @staticmethod
    def _order_is_active(order: OrderRead) -> bool:
        return str(order.status or "").lower() not in {"closed", "filled", "cancelled", "rejected"}

    @staticmethod
    def _live_state_label(value: str) -> str:
        return {
            "off": "ОСТАНОВЛЕН",
            "idle": "ОЖИДАНИЕ",
            "scanning": "СКАНИРОВАНИЕ",
            "signal_found": "СИГНАЛ НАЙДЕН",
            "waiting_approve": "ЖДЕТ РЕШЕНИЯ",
            "executing": "ОТКРЫТИЕ СДЕЛКИ",
            "order_open": "ПОЗИЦИЯ ОТКРЫТА",
            "error": "ОШИБКА",
        }.get(str(value or "").lower(), str(value or "--").upper())

    @staticmethod
    def _seconds_until(value: datetime | None) -> int | None:
        if value is None:
            return None
        now = datetime.now(UTC)
        target = value if value.tzinfo else value.replace(tzinfo=UTC)
        return max(int((target - now).total_seconds()), 0)

    def _build_status_card_text(self, snapshot: AutomationStateRead) -> str:
        universe = "ВЕСЬ РЫНОК" if snapshot.scan_market_wide else snapshot.symbol
        pending = len(snapshot.pending_approvals)
        account_label = "DEMO / TESTNET" if snapshot.trade_env == "testnet" else "REAL / БОЕВОЙ СЧЕТ"
        amount_label = "Маржа" if snapshot.market == "futures" else "Сумма"
        next_seconds = self._seconds_until(snapshot.next_check_at)
        progress = (
            f"Обработано: {snapshot.scan_processed_pairs}/{snapshot.scan_total_pairs}\n"
            if snapshot.scan_total_pairs
            else ""
        )
        cycle_result = (
            f"Сигналов: {snapshot.scan_matched_signals} · следующий цикл через "
            f"{next_seconds if next_seconds is not None else snapshot.poll_interval_sec} сек.\n"
            if snapshot.scan_phase == "complete"
            else ""
        )
        latest_signal = (
            f"{snapshot.latest_signal.signal_type.upper()} {snapshot.latest_signal.symbol} {snapshot.latest_signal.timeframe}"
            if snapshot.latest_signal
            else "--"
        )
        latest_order = (
            f"#{snapshot.latest_order.id} {snapshot.latest_order.side} {snapshot.latest_order.symbol} · {snapshot.latest_order.status}"
            if snapshot.latest_order
            else "--"
        )
        return (
            "ТОРГОВЫЙ COCKPIT\n\n"
            f"{'РАБОТАЕТ' if snapshot.enabled else 'ОСТАНОВЛЕН'} · {snapshot.mode.upper()} · {account_label}\n"
            f"Состояние: {self._live_state_label(snapshot.live_state)}\n"
            f"{snapshot.live_message or '--'}\n\n"
            f"Рынок: {snapshot.market.upper()} · {universe}\n"
            f"Вход: {snapshot.timeframe} · Тренд: {snapshot.trend_timeframe}\n"
            f"Риск: {self._risk_profile_label().upper()} · RR от 1:{snapshot.min_reward_risk:g}\n"
            f"{amount_label}: ${snapshot.quote_amount or 0:.2f} · Плечо: x{snapshot.leverage or 1}\n\n"
            f"{progress}"
            f"{cycle_result}"
            f"Ожидают решения: {pending}\n"
            f"Последний сигнал: {latest_signal}\n"
            f"Последний ордер: {latest_order}\n"
            f"Проверка: {self._format_time(snapshot.last_check_at)}"
        )

    def _build_live_card_text(self, snapshot: AutomationStateRead) -> str:
        active_orders = [order for order in snapshot.recent_orders if self._order_is_active(order)]
        next_seconds = self._seconds_until(snapshot.next_check_at)
        return (
            "ЖИВОЙ СТАТУС\n\n"
            f"Automation: {'ONLINE' if snapshot.worker_running else 'OFFLINE'}\n"
            f"Telegram: {'ONLINE' if snapshot.telegram_worker_running else 'OFFLINE'}\n"
            f"Торговля: {'ON' if snapshot.enabled else 'OFF'} · {snapshot.mode.upper()}\n"
            f"Цикл: {self._live_state_label(snapshot.live_state)}\n"
            f"{snapshot.live_message or '--'}\n\n"
            f"Обработано: {snapshot.scan_processed_pairs}/{snapshot.scan_total_pairs or '--'}\n"
            f"Сигналов в цикле: {snapshot.scan_matched_signals}\n"
            f"Следующий цикл: {next_seconds if next_seconds is not None else '--'} сек.\n\n"
            f"Открытых/активных ордеров: {len(active_orders)}\n"
            f"Pending approve: {len(snapshot.pending_approvals)}\n"
            f"Последняя проверка: {self._format_time(snapshot.last_check_at)}\n"
            f"Последний callback: {self._format_time(snapshot.last_callback_handled_at)}\n\n"
            f"Ошибка worker: {snapshot.last_error or '--'}\n"
            f"Ошибка Telegram: {snapshot.last_telegram_error or '--'}"
        )

    def _build_automation_card_text(self, snapshot: AutomationStateRead) -> str:
        return (
            "АВТОМАТИЗАЦИЯ\n\n"
            f"Worker: {'ЗАПУЩЕН' if snapshot.enabled else 'ОСТАНОВЛЕН'}\n"
            f"Режим: {snapshot.mode.upper()}\n"
            f"Счет: {'DEMO / TESTNET' if snapshot.trade_env == 'testnet' else 'REAL'}\n"
            f"Проверка каждые: {snapshot.poll_interval_sec} сек.\n\n"
            "SEMI: сигнал ждет твоего подтверждения.\n"
            "AUTO: вход, SL/TP и сопровождение выполняются автоматически."
        )

    def _build_market_card_text(self, snapshot: AutomationStateRead) -> str:
        universe = f"до {snapshot.max_pairs} пар" if snapshot.scan_market_wide else snapshot.symbol
        return (
            "РЫНОК И АНАЛИЗ\n\n"
            f"Тип рынка: {snapshot.market.upper()}\n"
            f"Источник данных: {snapshot.data_env.upper()}\n"
            f"Universe: {universe}\n"
            f"Пара по умолчанию: {snapshot.symbol}\n"
            f"ТФ входа: {snapshot.timeframe}\n"
            f"ТФ тренда: {snapshot.trend_timeframe}\n"
            f"История: {snapshot.lookback_days} дней"
        )

    def _build_risk_card_text(self, snapshot: AutomationStateRead) -> str:
        return (
            "РИСК И КАЧЕСТВО\n\n"
            f"Профиль: {self._risk_profile_label().upper()}\n"
            f"Confidence от: {round(snapshot.min_confidence * 100)}%\n"
            f"Подтверждений от: {snapshot.min_confirmations}\n"
            f"RR от: 1:{snapshot.min_reward_risk:g}\n"
            f"Фигура обязательна: {'да' if snapshot.require_pattern else 'нет'}\n"
            f"Объем обязателен: {'да' if snapshot.require_volume_confirm else 'нет'}\n\n"
            f"Сумма сделки: ${snapshot.quote_amount or 0:g}\n"
            f"Плечо: x{snapshot.leverage or 1}\n"
            f"SL/TP сразу: {'да' if snapshot.attach_orders else 'нет'}\n"
            f"Auto BE: {'да' if snapshot.auto_breakeven else 'нет'}"
        )

    def _build_execution_card_text(self, snapshot: AutomationStateRead) -> str:
        return (
            "ИСПОЛНЕНИЕ СДЕЛКИ\n\n"
            f"Сумма/маржа: ${snapshot.quote_amount or 0:g}\n"
            f"Авторасчет количества: {'да' if snapshot.auto_quantity else 'нет'}\n"
            f"Плечо: x{snapshot.leverage or 1}\n"
            f"Прикреплять SL/TP: {'да' if snapshot.attach_orders else 'нет'}\n"
            f"Переносить в BE: {'да' if snapshot.auto_breakeven else 'нет'}\n"
            f"Интервал сканирования: {snapshot.poll_interval_sec} сек."
        )

    def _build_pending_card_text(self, snapshot: AutomationStateRead) -> str:
        lines = ["ОЖИДАЮТ ТВОЕГО РЕШЕНИЯ", ""]
        if not snapshot.pending_approvals:
            lines.append("Очередь пуста. Новый сигнал появится здесь автоматически.")
        else:
            for item in snapshot.pending_approvals[:8]:
                lines.append(
                    f"#{item.signal_id} {item.signal_type.upper()} {item.symbol} {item.timeframe} · "
                    f"{round(item.confidence * 100)}% · entry {self._format_price(item.entry_price)}"
                )
        return "\n".join(lines)

    def _build_orders_card_text(self, snapshot: AutomationStateRead, active_only: bool = False) -> str:
        orders = [
            order for order in snapshot.recent_orders
            if not active_only or self._order_is_active(order)
        ]
        if not orders:
            return "ПОЗИЦИИ\n\nОткрытых позиций сейчас нет."
        lines = ["ПОЗИЦИИ" if active_only else "ИСТОРИЯ ОРДЕРОВ", ""]
        for order in orders[:8]:
            pnl = f"{float(order.realized_pnl):+.2f}%" if order.realized_pnl is not None else "--"
            lines.append(
                f"#{order.id} {order.side} {order.symbol} · {order.status}\n"
                f"entry {self._format_price(order.price)} · PnL {pnl}"
            )
        return "\n".join(lines)

    def _build_signals_card_text(self, snapshot: AutomationStateRead) -> str:
        if not snapshot.recent_signals:
            return "Signals\nСигналов пока нет."
        lines = ["СИГНАЛЫ", ""]
        for signal in snapshot.recent_signals[:8]:
            lines.append(
                f"#{signal.id} {signal.signal_type.upper()} {signal.symbol} {signal.timeframe} · "
                f"{round(float(signal.confidence or 0) * 100)}%"
            )
        return "\n".join(lines)

    def _build_signal_detail_text(self, signal: SignalRead, is_pending: bool) -> str:
        rationale = (signal.rationale or "Объяснение стратегии не записано.").strip()
        return (
            f"СИГНАЛ #{signal.id}\n\n"
            f"{signal.signal_type.upper()} {signal.symbol} · {signal.timeframe}\n"
            f"Уверенность: {round(float(signal.confidence or 0) * 100)}%\n"
            f"Entry: {self._format_price(signal.entry_price)}\n"
            f"SL: {self._format_price(signal.stop_loss)}\n"
            f"TP: {self._format_price(signal.take_profit)}\n"
            f"Статус: {'ЖДЕТ ПОДТВЕРЖДЕНИЯ' if is_pending else 'ИСТОРИЯ'}\n\n"
            f"Почему сигнал:\n{rationale[:1200]}\n\n"
            f"Создан: {self._format_time(signal.created_at)}"
        )

    def _build_order_detail_text(self, order: OrderRead) -> str:
        active = self._order_is_active(order)
        pnl = f"{float(order.realized_pnl):+.2f}%" if order.realized_pnl is not None else "--"
        position_value = float(order.price or 0) * float(order.quantity or 0)
        actual_margin = position_value / max(int(order.leverage or 1), 1) if order.market == "futures" else position_value
        amount_label = "Фактическая маржа" if order.market == "futures" else "Сумма позиции"
        return (
            f"ОРДЕР #{order.id}\n\n"
            f"{order.side} {order.symbol} · {order.market.upper()}\n"
            f"Статус: {order.status.upper()}\n"
            f"Счет: {(order.trade_env or '--').upper()}\n"
            f"Entry: {self._format_price(order.price)}\n"
            f"SL: {self._format_price(order.stop_loss)}\n"
            f"TP: {self._format_price(order.take_profit)}\n"
            f"Количество: {order.quantity:g}\n"
            f"Плечо: x{order.leverage or 1}\n"
            f"{amount_label}: ${actual_margin:.4f}\n"
            f"PnL: {pnl}\n"
            f"Защита: SL #{order.stop_order_id or '--'} · TP #{order.take_order_id or order.oco_order_id or '--'}\n\n"
            f"{'Позиция доступна для управления.' if active else 'Позиция завершена.'}\n"
            f"Создан: {self._format_time(order.created_at)}"
        )

    async def _build_diagnostics_text(self) -> str:
        stats = self._last_scan_stats
        if stats is None:
            return (
                "ДИАГНОСТИКА СКАНЕРА\n\n"
                "Завершенного market-wide скана пока нет.\n"
                "Нажми «Проверить сейчас», затем вернись сюда."
            )
        top_reasons = sorted(stats.reason_counts.items(), key=lambda item: item[1], reverse=True)[:6]
        lines = [
            "ДИАГНОСТИКА ПОСЛЕДНЕГО СКАНА",
            "",
            f"Всего инструментов: {stats.universe_pairs}",
            f"Подошли под universe: {stats.eligible_pairs}",
            f"Обработано: {stats.processed_pairs}",
            f"Найдено сигналов: {stats.matched_signals}",
        ]
        if top_reasons:
            lines.extend(["", "Почему пары отсеялись:"])
            lines.extend(f"- {reason}: {count}" for reason, count in top_reasons)
        else:
            lines.extend(["", "Причины отсева пока не записаны."])
        return "\n".join(lines)

    async def _render_telegram_view(self, chat_id: str, view: str, message_id: int | None = None) -> str:
        snapshot = await self.snapshot()
        session = self._get_telegram_session(chat_id)
        session.view = view
        if view == "pending":
            text = self._build_pending_card_text(snapshot)
            pending_ids = {item.signal_id for item in snapshot.pending_approvals}
            pending_signals = [signal for signal in snapshot.recent_signals if signal.id in pending_ids]
            reply_markup = self._telegram.signal_list_keyboard(pending_signals, pending_ids)
        elif view in {"orders", "positions"}:
            active_only = view == "positions"
            text = self._build_orders_card_text(snapshot, active_only=active_only)
            reply_markup = self._telegram.order_list_keyboard(snapshot.recent_orders, active_only=active_only)
        elif view == "signals":
            text = self._build_signals_card_text(snapshot)
            pending_ids = {item.signal_id for item in snapshot.pending_approvals}
            reply_markup = self._telegram.signal_list_keyboard(snapshot.recent_signals, pending_ids)
        elif view == "diagnostics":
            text = await self._build_diagnostics_text()
            reply_markup = self._telegram.navigation_keyboard()
        elif view == "live":
            text = self._build_live_card_text(snapshot)
            reply_markup = self._telegram.navigation_keyboard(
                [
                    [
                        {"text": "Позиции", "callback_data": "menu:positions"},
                        {"text": "Ожидают решения", "callback_data": "menu:pending"},
                    ],
                    [{"text": "Один цикл анализа", "callback_data": "control:run"}],
                ]
            )
        elif view == "automation":
            text = self._build_automation_card_text(snapshot)
            reply_markup = self._telegram.automation_keyboard(snapshot.enabled, snapshot.mode, snapshot.trade_env)
        elif view == "market":
            text = self._build_market_card_text(snapshot)
            reply_markup = self._telegram.market_keyboard(snapshot.market, snapshot.scan_market_wide)
        elif view == "pair":
            text = (
                "Выбор пары\n"
                f"Текущая пара: {snapshot.symbol}\n"
                f"Рынок: {snapshot.market.upper()}"
            )
            reply_markup = self._telegram.symbol_keyboard(snapshot.symbol, snapshot.market)
        elif view == "tf":
            text = (
                "Выбор таймфрейма\n"
                f"Текущий TF: {snapshot.timeframe}\n"
                f"Higher TF: {snapshot.trend_timeframe}"
            )
            reply_markup = self._telegram.timeframe_keyboard(snapshot.timeframe)
        elif view == "risk":
            text = self._build_risk_card_text(snapshot)
            reply_markup = self._telegram.risk_keyboard(self._risk_profile_label())
        elif view == "execution":
            text = self._build_execution_card_text(snapshot)
            reply_markup = self._telegram.execution_keyboard(
                snapshot.attach_orders,
                snapshot.auto_breakeven,
                snapshot.leverage,
            )
        elif view.startswith("signal-"):
            raw_id = view.removeprefix("signal-")
            signal = next((item for item in snapshot.recent_signals if str(item.id) == raw_id), None)
            if signal is None:
                text = "Сигнал не найден или уже вышел из короткой истории."
                reply_markup = self._telegram.navigation_keyboard(
                    [[{"text": "К сигналам", "callback_data": "menu:signals"}]]
                )
            else:
                pending_ids = {item.signal_id for item in snapshot.pending_approvals}
                text = self._build_signal_detail_text(signal, signal.id in pending_ids)
                reply_markup = (
                    self._telegram.signal_actions_keyboard(signal.id)
                    if signal.id in pending_ids
                    else self._telegram.navigation_keyboard(
                        [[{"text": "К сигналам", "callback_data": "menu:signals"}]]
                    )
                )
        elif view.startswith("order-"):
            raw_id = view.removeprefix("order-")
            order = next((item for item in snapshot.recent_orders if str(item.id) == raw_id), None)
            if order is None:
                text = "Ордер не найден или уже вышел из короткой истории."
                reply_markup = self._telegram.navigation_keyboard(
                    [[{"text": "К позициям", "callback_data": "menu:positions"}]]
                )
            else:
                text = self._build_order_detail_text(order)
                reply_markup = self._telegram.order_actions_keyboard(order.id, active=self._order_is_active(order))
        else:
            text = self._build_status_card_text(snapshot)
            reply_markup = self._telegram.main_menu_keyboard(snapshot.enabled)
            session.view = "home"

        if message_id:
            await self._telegram.edit_message_text(text, message_id=message_id, chat_id=chat_id, reply_markup=reply_markup)
            session.status_message_id = int(message_id)
            return text

        if session.status_message_id:
            try:
                await self._telegram.edit_message_text(
                    text,
                    message_id=session.status_message_id,
                    chat_id=chat_id,
                    reply_markup=reply_markup,
                )
                return text
            except Exception:
                session.status_message_id = None

        sent = await self._telegram.send_message(text, chat_id=chat_id, reply_markup=reply_markup)
        if sent and sent.get("message_id"):
            session.status_message_id = int(sent["message_id"])
        return text

    def _apply_risk_profile(self, profile: str) -> None:
        profile = str(profile or "").lower()
        if profile == "sniper":
            self.update_config(
                min_confidence=0.55,
                min_confirmations=2,
                require_pattern=False,
                require_volume_confirm=False,
                min_reward_risk=2.8,
                allow_candidate_patterns=False,
                quality_mode="sniper",
            )
            return
        if profile == "aggressive":
            self.update_config(
                min_confidence=0.3,
                min_confirmations=1,
                require_pattern=False,
                require_volume_confirm=False,
                min_reward_risk=2.0,
                allow_candidate_patterns=True,
                quality_mode="aggressive",
            )
            return
        self.update_config(
            min_confidence=0.4,
            min_confirmations=1,
            require_pattern=False,
            require_volume_confirm=False,
            min_reward_risk=2.2,
            allow_candidate_patterns=True,
            quality_mode="balanced",
        )

    async def _telegram_loop(self) -> None:
        while True:
            try:
                updates = await self._telegram.get_updates(self._updates_offset)
                for update in updates:
                    self._updates_offset = max(self._updates_offset, int(update.get("update_id", 0)) + 1)
                    await self._handle_telegram_update(update)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_telegram_error = str(exc)
                self._add_log("error", "telegram_poll_error", str(exc)[:500])
            await asyncio.sleep(2)

    async def _handle_telegram_update(self, update: dict) -> None:
        self._last_update_received_at = datetime.now(UTC)
        callback_query = update.get("callback_query")
        if callback_query:
            message = callback_query.get("message") or {}
            chat_id = str((message.get("chat") or {}).get("id") or "").strip()
            if not self._is_authorized_chat(chat_id):
                callback_id = str(callback_query.get("id") or "")
                if callback_id:
                    await self._telegram.answer_callback_query(callback_id, "Этот чат не авторизован")
                return
            callback_id = str(callback_query.get("id") or "")
            if callback_id and callback_id in self._processed_callbacks:
                await self._telegram.answer_callback_query(callback_id, "Уже обработано")
                return
            if callback_id:
                self._processed_callbacks.add(callback_id)
                if len(self._processed_callbacks) > 500:
                    self._processed_callbacks = set(list(self._processed_callbacks)[-250:])
            try:
                reply = await self._handle_callback_query(callback_query)
            except Exception as exc:
                reply = f"Ошибка: {str(exc)[:150]}"
                self._last_telegram_error = str(exc)
                self._add_log("error", "telegram_callback_error", str(exc)[:500])
            finally:
                self._last_callback_handled_at = datetime.now(UTC)
                if callback_id:
                    await self._telegram.answer_callback_query(callback_id, reply[:180] if reply else "Готово")
            return
        message = update.get("message") or update.get("edited_message") or {}
        text = str(message.get("text") or "").strip()
        chat_id = str((message.get("chat") or {}).get("id") or "").strip()
        if not self._is_authorized_chat(chat_id):
            await self._telegram.send_message("Этот чат не авторизован.", chat_id=chat_id)
            return
        session = self._get_telegram_session(chat_id)
        if session.awaiting_input:
            reply = await self._handle_telegram_input(session, text)
            await self._telegram.send_message(reply, chat_id=chat_id, reply_markup=self._telegram.default_keyboard())
            await self._render_telegram_view(chat_id, session.view)
            return
        normalized = self._normalize_button_text(text)
        if normalized in {"/status-card", "/refresh-card", "/menu", "/pair-menu", "/tf-menu", "/risk-menu", "/diagnostics", "/start", "/help"}:
            view_map = {
                "/status-card": "home",
                "/refresh-card": "home",
                "/menu": "home",
                "/pair-menu": "pair",
                "/tf-menu": "tf",
                "/risk-menu": "risk",
                "/diagnostics": "diagnostics",
                "/start": "home",
                "/help": "home",
            }
            await self._render_telegram_view(chat_id, view_map[normalized])
            return
        if normalized in {"/pending", "/orders", "/positions", "/signals"}:
            view = (
                "pending"
                if normalized == "/pending"
                else "positions"
                if normalized == "/positions"
                else "orders"
                if normalized == "/orders"
                else "signals"
            )
            await self._render_telegram_view(chat_id, view)
            return
        if normalized.startswith("/mode ") or normalized.startswith("/env ") or normalized.startswith("/market "):
            await self._handle_telegram_command(text)
            await self._render_telegram_view(chat_id, "home")
            return
        if normalized.startswith("/universe ") or normalized.startswith("/symbol ") or normalized.startswith("/tf "):
            await self._handle_telegram_command(text)
            await self._render_telegram_view(chat_id, "home")
            return
        if normalized in {"/enable", "/disable", "/toggle", "/run"}:
            await self._handle_telegram_command(text)
            await self._render_telegram_view(chat_id, "home")
            return
        reply = await self._handle_telegram_command(text)
        await self._telegram.send_message(reply, chat_id=chat_id, reply_markup=self._telegram.default_keyboard())

    async def _handle_telegram_input(self, session: TelegramSession, text: str) -> str:
        action = session.awaiting_input
        target_id = session.target_id
        session.awaiting_input = None
        session.target_id = None
        raw = str(text or "").strip().replace(",", ".")
        if raw.lower() in {"cancel", "отмена", "/cancel"}:
            return "Ввод отменен."
        try:
            value = float(raw)
        except ValueError:
            return "Не удалось прочитать число. Действие отменено."
        if value <= 0:
            return "Значение должно быть больше нуля. Действие отменено."
        if action in {"sl", "tp"} and target_id:
            result = await self._handle_order_command(f"/{action}", [f"/{action}", str(target_id), str(value)])
            session.view = f"order-{target_id}"
            return result
        if action == "amount":
            self.update_config(quote_amount=value, auto_quantity=True)
            session.view = "execution"
            return f"Сумма сделки изменена на ${value:g}."
        if action == "poll":
            self.update_config(poll_interval_sec=int(value))
            session.view = "execution"
            return f"Интервал проверки изменен на {self._config.poll_interval_sec} сек."
        return "Действие уже не актуально."

    async def _handle_telegram_command(self, text: str) -> str:
        normalized_text = self._normalize_button_text(text)
        parts = normalized_text.split()
        command = parts[0].lower()
        if command in {"/help", "/start"}:
            return (
                "Бот готов. Основное управление теперь лучше делать кнопками.\n"
                "Fallback команды:\n"
                "/status\n/orders\n/pending\n/approve <signal_id>\n/reject <signal_id>\n"
                "/close <order_id>\n/be <order_id>\n/sl <order_id> <price>\n/tp <order_id> <price>\n"
                "/mode <semi|auto>\n/env <real|testnet>\n/market <spot|futures>\n/universe <market|single>\n"
                "/symbol <BTCUSDT>\n/tf <1h>\n/enable\n/disable\n/run"
            )
        if command == "/status":
            snapshot = await self.snapshot()
            return (
                f"Automation: {'ON' if snapshot.enabled else 'OFF'} · {snapshot.mode.upper()}\n"
                f"LIVE: {snapshot.live_state.upper()} · {snapshot.live_message or '--'}\n"
                f"{'MARKET-WIDE' if snapshot.scan_market_wide else snapshot.symbol} {snapshot.timeframe} · {snapshot.market} · {snapshot.trade_env}\n"
                f"Pending approvals: {len(snapshot.pending_approvals)}\n"
                f"Last signal: {snapshot.latest_signal.signal_type.upper() + ' ' + snapshot.latest_signal.timeframe if snapshot.latest_signal else '--'}\n"
                f"Last order: {snapshot.latest_order.status if snapshot.latest_order else '--'}\n"
                f"Last no-signal: {snapshot.last_no_signal_reason or '--'}"
            )
        if command == "/orders":
            snapshot = await self.snapshot()
            if not snapshot.recent_orders:
                return "Активных automation-ордеров пока нет."
            return self._build_orders_card_text(snapshot)
        if command == "/signals":
            snapshot = await self.snapshot()
            return self._build_signals_card_text(snapshot)
        if command == "/diagnostics":
            return await self._build_diagnostics_text()
        if command == "/pending":
            snapshot = await self.snapshot()
            if not snapshot.pending_approvals:
                return "Очередь approve пустая."
            return "\n".join(
                f"#{item.signal_id} {item.signal_type.upper()} {item.symbol} {item.timeframe} · {round(item.confidence * 100)}%"
                for item in snapshot.pending_approvals[:10]
            )
        if command == "/approve" and len(parts) >= 2:
            order = await self.approve(int(parts[1]))
            return f"Сигнал {parts[1]} подтвержден. Ордер #{order.id} {order.status}." if order else "Не удалось подтвердить сигнал."
        if command == "/reject" and len(parts) >= 2:
            return "Сигнал отклонен." if self.reject(int(parts[1])) else "Сигнал не найден."
        if command == "/mode" and len(parts) >= 2:
            self.set_mode(parts[1])
            return f"Режим переключен на {self._config.mode.upper()}."
        if command == "/env" and len(parts) >= 2:
            self.set_trade_env(parts[1])
            return f"Trade env: {self._config.trade_env}."
        if command == "/market" and len(parts) >= 2:
            self.update_config(market=parts[1])
            return f"Market: {self._config.market}."
        if command == "/universe" and len(parts) >= 2:
            self.update_config(scan_market_wide=(parts[1].lower() != "single"))
            return f"Universe: {'market-wide' if self._config.scan_market_wide else 'single'}."
        if command == "/symbol" and len(parts) >= 2:
            self.update_config(symbol=parts[1])
            return f"Symbol: {self._config.symbol}."
        if command in {"/tf", "/timeframe"} and len(parts) >= 2:
            self.update_config(timeframe=parts[1], h1_timeframe=parts[1])
            return f"Timeframe: {self._config.timeframe}."
        if command == "/enable":
            self.set_enabled(True)
            await self.run_cycle_now()
            snapshot = await self.snapshot()
            return f"Automation включена. LIVE: {snapshot.live_state.upper()} · {snapshot.live_message or '--'}"
        if command == "/disable":
            self.set_enabled(False)
            return "Automation остановлена."
        if command == "/toggle":
            if self._config.enabled:
                self.set_enabled(False)
                return "Automation остановлена."
            self.set_enabled(True)
            await self.run_cycle_now()
            return "Automation включена, первый цикл анализа выполнен."
        if command == "/run":
            await self.run_cycle_now()
            return "Принудительный цикл анализа выполнен."
        if command in {"/close", "/be", "/sl", "/tp"}:
            return await self._handle_order_command(command, parts)
        return "Команда не распознана. Используй /help."

    async def _handle_callback_query(self, callback_query: dict) -> str:
        data = str(callback_query.get("data") or "")
        message = callback_query.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id") or "").strip()
        message_id = int(message.get("message_id") or 0)
        if ":" not in data:
            return "Неизвестное действие."
        parts = data.split(":")
        action = parts[0]
        if action == "menu":
            view = parts[1] if len(parts) > 1 else "home"
            if view == "refresh":
                mapped = self._get_telegram_session(chat_id).view
            else:
                mapped = "home" if view == "home" else view
            await self._render_telegram_view(chat_id, mapped, message_id=message_id)
            return "Карточка обновлена."
        if action == "control" and len(parts) > 1:
            control = parts[1]
            if control == "enable":
                self.set_enabled(True)
                self._live_state = "scanning"
                self._live_message = "Первый цикл анализа запущен."
                asyncio.create_task(self._run_cycle_safe(), name="telegram-enable-scan")
            elif control == "disable":
                self.set_enabled(False)
            elif control == "run":
                self._live_state = "scanning"
                self._live_message = "Ручной цикл анализа запущен."
                asyncio.create_task(self._run_cycle_safe(), name="telegram-manual-scan")
            destination = "automation" if control in {"enable", "disable"} else "live"
            await self._render_telegram_view(chat_id, destination, message_id=message_id)
            return "Команда выполнена."
        if action == "config" and len(parts) > 2:
            group = parts[1]
            value = parts[2]
            if group == "mode":
                self.set_mode(value)
            elif group == "env":
                self.set_trade_env(value)
            elif group == "market":
                self.update_config(market=value)
            elif group == "universe":
                self.update_config(scan_market_wide=(value != "single"))
            elif group == "tf":
                trend_tf = "4h" if value in {"15m", "1h"} else value
                self.update_config(timeframe=value, h1_timeframe=value, trend_timeframe=trend_tf)
            elif group == "symbol":
                self.update_config(symbol=value, scan_market_wide=False)
            elif group == "risk":
                self._apply_risk_profile(value)
            elif group == "attach":
                self.update_config(attach_orders=value == "1")
            elif group == "be":
                self.update_config(auto_breakeven=value == "1")
            elif group == "lev":
                leverage = int(self._config.leverage or 1)
                leverage += 1 if value == "up" else -1
                self.update_config(leverage=min(max(leverage, 1), 125))
            next_view = "home"
            if group == "tf":
                next_view = "tf"
            elif group == "symbol":
                next_view = "pair"
            elif group == "risk":
                next_view = "risk"
            elif group in {"market", "universe"}:
                next_view = "market"
            elif group in {"mode", "env"}:
                next_view = "automation"
            elif group in {"attach", "be", "lev"}:
                next_view = "execution"
            await self._render_telegram_view(chat_id, next_view, message_id=message_id)
            return "Настройка обновлена."
        if action == "input" and len(parts) > 2:
            input_action = parts[1]
            raw_id = parts[2]
            session = self._get_telegram_session(chat_id)
            session.awaiting_input = input_action
            session.target_id = int(raw_id) if raw_id.isdigit() and int(raw_id) > 0 else None
            prompt = {
                "sl": "Отправь новую цену Stop Loss одним сообщением. Для отмены: Отмена",
                "tp": "Отправь новую цену Take Profit одним сообщением. Для отмены: Отмена",
                "amount": "Отправь сумму/маржу сделки в USDT. Для отмены: Отмена",
                "poll": "Отправь интервал проверки в секундах (15-900). Для отмены: Отмена",
            }.get(input_action, "Отправь числовое значение.")
            await self._telegram.send_message(prompt, chat_id=chat_id, reply_markup=self._telegram.default_keyboard())
            return "Жду значение."
        if action == "order" and len(parts) > 1 and parts[1].isdigit():
            await self._render_telegram_view(chat_id, f"order-{parts[1]}", message_id=message_id)
            return "Ордер открыт."
        if action == "signal" and len(parts) > 1 and parts[1].isdigit():
            await self._render_telegram_view(chat_id, f"signal-{parts[1]}", message_id=message_id)
            return "Сигнал открыт."
        if action == "nudge" and len(parts) == 4:
            level, direction, raw_id = parts[1], parts[2], parts[3]
            if level not in {"sl", "tp"} or direction not in {"-1", "1"} or not raw_id.isdigit():
                return "Некорректная корректировка."
            result = await self._nudge_order_level(int(raw_id), level, int(direction))
            await self._render_telegram_view(chat_id, f"order-{raw_id}", message_id=message_id)
            return result
        action, raw_id = data.split(":", 1)
        if not raw_id.isdigit():
            return "Некорректный идентификатор."
        identifier = int(raw_id)
        if action == "approve":
            order = await self.approve(identifier)
            if order:
                await self._render_telegram_view(chat_id, f"order-{order.id}", message_id=message_id)
                return f"Сигнал подтвержден. Ордер #{order.id} {order.status}."
            return "Не удалось подтвердить сигнал."
        if action == "reject":
            rejected = self.reject(identifier)
            await self._render_telegram_view(chat_id, "pending", message_id=message_id)
            return "Сигнал отклонен." if rejected else "Сигнал не найден."
        if action in {"close", "be"}:
            result = await self._handle_order_command(f"/{action}", [f"/{action}", str(identifier)])
            await self._render_telegram_view(chat_id, f"order-{identifier}", message_id=message_id)
            return result
        return "Неизвестное действие."

    async def _nudge_order_level(self, order_id: int, level: str, direction: int) -> str:
        async with self._session_manager.session_factory()() as session:
            order = await OrderRepository(session).get(order_id)
            if not order:
                return "Ордер не найден."
            current = order.stop_loss if level == "sl" else order.take_profit
            base = float(current or order.price or 0)
        if base <= 0:
            return "Для корректировки нет базовой цены."
        price = base * (1 + direction * 0.0025)
        return await self._handle_order_command(
            f"/{level}",
            [f"/{level}", str(order_id), str(price)],
        )

    async def _handle_order_command(self, command: str, parts: list[str]) -> str:
        if len(parts) < 2:
            return "Нужен order_id."
        order_id = int(parts[1])
        async with self._session_manager.session_factory()() as session:
            if command == "/close":
                from app.api.routes.orders import close_order_position

                order = await close_order_position(order_id, session=session)
                return f"Order #{order.id} close => {order.status}"
            if command == "/be":
                from app.api.routes.orders import move_to_breakeven

                order = await move_to_breakeven(order_id, session=session)
                return f"Order #{order.id} SL moved to BE."
            if len(parts) < 3:
                return "Нужна цена."
            price = float(parts[2])
            from app.schemas.order_stop_update import OrderStopUpdate
            if command == "/sl":
                from app.api.routes.orders import move_stop

                order = await move_stop(order_id, OrderStopUpdate(price=price), session=session)
                return f"Order #{order.id} new SL: {order.stop_loss}"
            from app.api.routes.orders import move_take

            order = await move_take(order_id, OrderStopUpdate(price=price), session=session)
            return f"Order #{order.id} new TP: {order.take_profit}"

    def _signal_fingerprint(self, symbol: str, timeframe: str, signal_payload: dict) -> str:
        entry = float(signal_payload.get("entry_price") or 0)
        stop = float(signal_payload.get("stop_loss") or 0)
        side = str(signal_payload.get("signal_type") or "")
        return f"{symbol}:{timeframe}:{side}:{round(entry, 5)}:{round(stop, 5)}"

    def _format_signal_message(self, signal: Signal, auto: bool) -> str:
        action = "AUTO EXECUTE" if auto else "APPROVAL NEEDED"
        return (
            f"{action}\n"
            f"{signal.signal_type.upper()} {signal.symbol} {signal.timeframe}\n"
            f"Entry: {signal.entry_price}\nSL: {signal.stop_loss}\nTP: {signal.take_profit}\n"
            f"Conf: {round(float(signal.confidence or 0) * 100)}%\n"
            f"Signal ID: {signal.id}"
        )

    def _normalize_button_text(self, text: str) -> str:
        raw = str(text or "").strip()
        mapping = {
            "Статус": "/status",
            "Статус-карта": "/status-card",
            "Панель": "/status-card",
            "Обновить": "/refresh-card",
            "Меню": "/menu",
            "Очередь": "/pending",
            "Ордеры": "/orders",
            "Позиции": "/positions",
            "Сигналы": "/signals",
            "Старт": "/enable",
            "Стоп": "/disable",
            "Проверить сейчас": "/run",
            "Проверить рынок": "/run",
            "Запуск / Стоп": "/toggle",
            "SEMI": "/mode semi",
            "AUTO": "/mode auto",
            "DEMO": "/env testnet",
            "REAL": "/env real",
            "Рынок: Spot": "/market spot",
            "Рынок: Futures": "/market futures",
            "Все пары": "/universe market",
            "Одна пара": "/universe single",
            "Пара": "/pair-menu",
            "ТФ": "/tf-menu",
            "Риск": "/risk-menu",
            "Диагностика": "/diagnostics",
        }
        return mapping.get(raw, raw if raw.startswith("/") else "/help")

    def _config_snapshot_meta(self) -> dict:
        return {
            "symbol": self._config.symbol,
            "scan_market_wide": self._config.scan_market_wide,
            "quote": self._config.quote,
            "max_pairs": self._config.max_pairs,
            "timeframe": self._config.timeframe,
            "market": self._config.market,
            "mode": self._config.mode,
            "trade_env": self._config.trade_env,
        }

    def _add_log(self, level: str, event: str, message: str, meta: dict | None = None) -> None:
        self._logs.insert(
            0,
            AutomationLog(
                id=uuid4().hex,
                level=level,
                event=event,
                message=message,
                created_at=datetime.now(UTC),
                meta=meta,
            ),
        )
        self._logs = self._logs[:100]


_runtime: AutomationRuntime | None = None


def get_automation_runtime() -> AutomationRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AutomationRuntime(Settings())
    return _runtime
