from __future__ import annotations

from dataclasses import dataclass

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
    timeframe: str
    confidence: float
    volatility_score: float
    rank: float
    signal: Signal


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

        results: list[ScanResultItem] = []
        for pair in filtered:
            symbol = pair["symbol"]
            candles = await self._candle_repository.latest(symbol, timeframe, limit=lookback)
            if len(candles) < lookback and auto_sync:
                await self._market_data_service.sync_history(
                    symbol,
                    timeframe,
                    lookback_days=lookback_days,
                    market=market,
                    binance_symbol=pair.get("symbol"),
                )
                candles = await self._candle_repository.latest(symbol, timeframe, limit=lookback)
            if len(candles) < lookback:
                continue

            data = candles_to_df(candles)

            signal_payload = self._strategy.evaluate(data)
            if not signal_payload:
                continue

            if store_signals:
                signal = Signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_payload["signal_type"],
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
                    signal_type=signal_payload["signal_type"],
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
                    timeframe=timeframe,
                    confidence=signal_payload.get("confidence", 0),
                    volatility_score=volatility_score,
                    rank=rank,
                    signal=signal,
                )
            )

        results.sort(key=lambda item: item.rank, reverse=True)
        return results[:limit]
