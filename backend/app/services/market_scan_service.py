from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable

import pandas as pd

from app.repositories.candle_repository import CandleRepository
from app.repositories.signal_repository import SignalRepository
from app.services.binance_candle_service import BinanceCandleService
from app.services.binance_market_service import BinanceMarketService
from app.services.market_data_service import MarketDataService
from app.strategies.base_strategy import BaseStrategy
from app.models.signal import Signal
from app.utils.candle_frame import candles_to_df
from app.utils.jsonable import to_jsonable


@dataclass
class ScanResultItem:
    symbol: str
    binance_symbol: str
    chart_symbol: str
    chart_url: str
    timeframe: str
    confidence: float
    volatility_score: float
    rank: float
    signal: Signal
    is_new: bool = False


@dataclass
class ScanRunStats:
    mode: str
    selected_symbol: str | None
    universe_pairs: int
    eligible_pairs: int
    processed_pairs: int
    matched_signals: int
    reason_counts: dict[str, int]


class MarketScanService:
    def __init__(
        self,
        candle_repository: CandleRepository,
        signal_repository: SignalRepository,
        market_service: BinanceMarketService,
        strategy: BaseStrategy,
        binance_service: BinanceCandleService | None = None,
    ) -> None:
        self._candle_repository = candle_repository
        self._signal_repository = signal_repository
        self._market_service = market_service
        self._strategy = strategy
        self._market_data_service = MarketDataService(candle_repository, binance_service)

    def _chart_url(self, market: str, symbol: str) -> str:
        normalized = symbol.replace("-", "").upper()
        if market.lower() == "futures":
            return f"https://www.binance.com/en/futures/{normalized}"
        return f"https://www.binance.com/en/trade/{normalized}?type=spot"

    async def scan(
        self,
        market: str,
        timeframe: str,
        lookback: int,
        lookback_days: int,
        quote: str,
        min_volatility: float,
        max_pairs: int,
        limit: int,
        auto_sync: bool,
        store_signals: bool,
        only_new_signals_minutes: int = 0,
        symbol: str | None = None,
        market_wide: bool = True,
        progress_callback: Callable[[int, int, int, str], Awaitable[None] | None] | None = None,
        stop_after_limit: bool = False,
    ) -> tuple[list[ScanResultItem], ScanRunStats]:
        pairs = await self._market_service.list_pairs(market)
        universe_pairs = len(pairs)
        filtered = [
            pair
            for pair in pairs
            if (not quote or pair.get("quote_asset") == quote)
            and pair.get("volatility_score", 0) >= min_volatility
        ]
        eligible_pairs = len(filtered)
        filtered.sort(key=lambda item: item.get("volatility_score", 0), reverse=True)
        selected_symbol = str(symbol or "").upper().replace("-", "")
        mode = "market_wide" if market_wide else "single_pair"
        if market_wide:
            filtered = filtered[:max_pairs]
        elif selected_symbol:
            filtered = [pair for pair in filtered if str(pair.get("symbol") or "").upper() == selected_symbol]
        else:
            filtered = []

        trend_tf = (
            getattr(self._strategy, "trend_timeframe", None)
            or getattr(self._strategy, "h1_timeframe", "1h")
        ) if getattr(self._strategy, "is_mtf", False) else None

        results: list[ScanResultItem] = []
        processed_pairs = 0
        reason_counts: dict[str, int] = {}
        new_threshold = (
            datetime.utcnow() - timedelta(minutes=max(0, int(only_new_signals_minutes)))
            if only_new_signals_minutes > 0
            else None
        )
        total_pairs = len(filtered)
        for index, pair in enumerate(filtered, start=1):
            symbol = pair["symbol"]
            if auto_sync:
                await self._safe_sync(symbol, timeframe, lookback_days, market, pair.get("symbol"))
                if trend_tf and trend_tf != timeframe:
                    await self._safe_sync(symbol, trend_tf, lookback_days, market, pair.get("symbol"))
                await self._report_progress(progress_callback, index, total_pairs, len(results), "history")

            candles = await self._candle_repository.latest(symbol, timeframe, limit=lookback)
            if len(candles) < lookback:
                reason_counts["no_candles_in_db"] = reason_counts.get("no_candles_in_db", 0) + 1
                await self._report_progress(progress_callback, index, total_pairs, len(results), "analysis")
                continue
            processed_pairs += 1

            data = candles_to_df(candles)
            context: dict | None = None
            if getattr(self._strategy, "is_mtf", False):
                trend_tf = getattr(self._strategy, "trend_timeframe", None) or getattr(self._strategy, "h1_timeframe", "1h")
                trend_candles = await self._candle_repository.latest(symbol, trend_tf, limit=300)
                if trend_candles:
                    context = {
                        "trend_data": candles_to_df(trend_candles),
                        "h1_data": candles_to_df(trend_candles),  # legacy compat
                        "timeframe": timeframe,
                    }
                else:
                    reason_counts["no_trend_data_or_insufficient"] = reason_counts.get("no_trend_data_or_insufficient", 0) + 1
                    await self._report_progress(progress_callback, index, total_pairs, len(results), "analysis")
                    continue
            elif context is None:
                context = {"timeframe": timeframe}

            if getattr(self._strategy, "requires_order_book", False):
                try:
                    context = context or {"timeframe": timeframe}
                    context["order_book"] = await self._market_service.order_book(
                        market,
                        pair.get("symbol") or symbol,
                        limit=50,
                    )
                except Exception:
                    reason_counts["order_book_unavailable"] = reason_counts.get("order_book_unavailable", 0) + 1

            signal_payload = self._strategy.evaluate(data, context)
            if not signal_payload:
                debug = self._strategy.explain(data, context)
                reasons = list(debug.get("reasons") or [])
                primary = reasons[0] if reasons else "no_signal_components"
                reason_counts[primary] = reason_counts.get(primary, 0) + 1
                await self._report_progress(progress_callback, index, total_pairs, len(results), "analysis")
                continue

            signal_type = signal_payload["signal_type"]
            is_duplicate_recent = False
            if new_threshold is not None:
                is_duplicate_recent = await self._signal_repository.has_recent(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    since=new_threshold,
                )
                if is_duplicate_recent:
                    reason_counts["duplicate_recent"] = reason_counts.get("duplicate_recent", 0) + 1
                    await self._report_progress(progress_callback, index, total_pairs, len(results), "analysis")
                    continue

            if store_signals:
                signal = Signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    confidence=to_jsonable(signal_payload["confidence"]),
                    entry_price=to_jsonable(signal_payload.get("entry_price")),
                    stop_loss=to_jsonable(signal_payload.get("stop_loss")),
                    take_profit=to_jsonable(signal_payload.get("take_profit")),
                    meta=to_jsonable(signal_payload.get("meta")),
                    rationale=signal_payload.get("rationale"),
                )
                signal = await self._signal_repository.add(signal)
            else:
                signal = Signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    confidence=to_jsonable(signal_payload["confidence"]),
                    entry_price=to_jsonable(signal_payload.get("entry_price")),
                    stop_loss=to_jsonable(signal_payload.get("stop_loss")),
                    take_profit=to_jsonable(signal_payload.get("take_profit")),
                    meta=to_jsonable(signal_payload.get("meta")),
                    rationale=signal_payload.get("rationale"),
                )

            volatility_score = float(pair.get("volatility_score", 0))
            rank = float(signal_payload.get("confidence", 0)) * 100 + volatility_score
            results.append(
                ScanResultItem(
                    symbol=symbol,
                    binance_symbol=pair["symbol"],
                    chart_symbol=symbol.replace("-", "").upper(),
                    chart_url=self._chart_url(market, pair["symbol"]),
                    timeframe=timeframe,
                    confidence=signal_payload.get("confidence", 0),
                    volatility_score=volatility_score,
                    rank=rank,
                    signal=signal,
                    is_new=bool(new_threshold is not None and not is_duplicate_recent),
                )
            )
            await self._report_progress(progress_callback, index, total_pairs, len(results), "analysis")
            if stop_after_limit and len(results) >= limit:
                break

        results.sort(key=lambda item: item.rank, reverse=True)
        limited = results[:limit]
        return limited, ScanRunStats(
            mode=mode,
            selected_symbol=selected_symbol or None,
            universe_pairs=universe_pairs,
            eligible_pairs=eligible_pairs,
            processed_pairs=processed_pairs,
            matched_signals=len(limited),
            reason_counts=reason_counts,
        )

    async def _report_progress(
        self,
        callback: Callable[[int, int, int, str], Awaitable[None] | None] | None,
        processed: int,
        total: int,
        matched: int,
        phase: str,
    ) -> None:
        if callback is None:
            return
        result = callback(processed, total, matched, phase)
        if inspect.isawaitable(result):
            await result

    async def _safe_sync(
        self,
        symbol: str,
        timeframe: str,
        lookback_days: int,
        market: str,
        binance_symbol: str | None,
    ) -> None:
        """Sync history for a symbol+timeframe, swallowing errors."""
        try:
            await self._market_data_service.sync_history(
                symbol,
                timeframe,
                lookback_days=lookback_days,
                market=market,
                binance_symbol=binance_symbol or symbol,
            )
        except Exception:
            pass
