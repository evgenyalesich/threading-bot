from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from app.repositories.candle_repository import CandleRepository
from app.repositories.signal_repository import SignalRepository
from app.services.binance_candle_service import BinanceCandleService
from app.services.binance_market_service import BinanceMarketService
from app.services.market_data_service import MarketDataService
from app.strategies.base_strategy import BaseStrategy
from app.models.signal import Signal
from app.utils.candle_frame import candles_to_df


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
    ) -> list[ScanResultItem]:
        pairs = await self._market_service.list_pairs(market)
        filtered = [
            pair
            for pair in pairs
            if (not quote or pair.get("quote_asset") == quote)
            and pair.get("volatility_score", 0) >= min_volatility
        ]
        filtered.sort(key=lambda item: item.get("volatility_score", 0), reverse=True)
        filtered = filtered[:max_pairs]

        # Sync all entry + trend timeframes in parallel before processing
        if auto_sync and filtered:
            trend_tf = (
                getattr(self._strategy, "trend_timeframe", None)
                or getattr(self._strategy, "h1_timeframe", "1h")
            ) if getattr(self._strategy, "is_mtf", False) else None

            sync_tasks = []
            for pair in filtered:
                symbol = pair["symbol"]
                # Sync entry timeframe
                sync_tasks.append(
                    self._safe_sync(symbol, timeframe, lookback_days, market, pair.get("symbol"))
                )
                # Sync trend timeframe if MTF strategy needs it
                if trend_tf and trend_tf != timeframe:
                    sync_tasks.append(
                        self._safe_sync(symbol, trend_tf, lookback_days, market, pair.get("symbol"))
                    )
            # Run all syncs concurrently (cap at 10 at a time to avoid overloading Binance)
            sem = asyncio.Semaphore(10)
            async def _limited(coro):
                async with sem:
                    return await coro
            await asyncio.gather(*[_limited(t) for t in sync_tasks])

        results: list[ScanResultItem] = []
        new_threshold = (
            datetime.utcnow() - timedelta(minutes=max(0, int(only_new_signals_minutes)))
            if only_new_signals_minutes > 0
            else None
        )
        for pair in filtered:
            symbol = pair["symbol"]
            candles = await self._candle_repository.latest(symbol, timeframe, limit=lookback)
            if len(candles) < lookback:
                continue

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
            elif context is None:
                context = {"timeframe": timeframe}

            signal_payload = self._strategy.evaluate(data, context)
            if not signal_payload:
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
                    continue

            if store_signals:
                signal = Signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    confidence=signal_payload["confidence"],
                    entry_price=signal_payload.get("entry_price"),
                    stop_loss=signal_payload.get("stop_loss"),
                    take_profit=signal_payload.get("take_profit"),
                    meta=signal_payload.get("meta"),
                    rationale=signal_payload.get("rationale"),
                )
                signal = await self._signal_repository.add(signal)
            else:
                signal = Signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    confidence=signal_payload["confidence"],
                    entry_price=signal_payload.get("entry_price"),
                    stop_loss=signal_payload.get("stop_loss"),
                    take_profit=signal_payload.get("take_profit"),
                    meta=signal_payload.get("meta"),
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

        results.sort(key=lambda item: item.rank, reverse=True)
        return results[:limit]

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
