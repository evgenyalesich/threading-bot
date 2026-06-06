from __future__ import annotations

import pandas as pd

from app.models.signal import Signal
from app.repositories.candle_repository import CandleRepository
from app.repositories.signal_repository import SignalRepository
from app.services.binance_market_service import BinanceMarketService
from app.strategies.base_strategy import BaseStrategy
from app.utils.jsonable import to_jsonable
from app.utils.candle_frame import candles_to_df


class SignalService:
    def __init__(
        self,
        candle_repository: CandleRepository,
        signal_repository: SignalRepository,
        strategy: BaseStrategy,
        market_service: BinanceMarketService | None = None,
        market: str = "futures",
    ) -> None:
        self._candle_repository = candle_repository
        self._signal_repository = signal_repository
        self._strategy = strategy
        self._market_service = market_service
        self._market = market

    async def run(self, symbol: str, timeframe: str, lookback: int = 500) -> Signal | None:
        candles = await self._candle_repository.latest(symbol, timeframe, limit=lookback)
        if not candles:
            return None

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

        if getattr(self._strategy, "requires_order_book", False) and self._market_service is not None:
            try:
                context = context or {"timeframe": timeframe}
                context["order_book"] = await self._market_service.order_book(self._market, symbol, limit=50)
            except Exception:
                context = context or {"timeframe": timeframe}
                context["order_book_error"] = "unavailable"

        signal_payload = self._strategy.evaluate(data, context)
        if not signal_payload:
            return None

        signal = Signal(
            symbol=symbol,
            timeframe=timeframe,
            signal_type=signal_payload["signal_type"],
            confidence=float(signal_payload["confidence"]),
            entry_price=to_jsonable(signal_payload.get("entry_price")),
            stop_loss=to_jsonable(signal_payload.get("stop_loss")),
            take_profit=to_jsonable(signal_payload.get("take_profit")),
            meta=to_jsonable(signal_payload.get("meta")),
            rationale=signal_payload.get("rationale"),
        )
        return await self._signal_repository.add(signal)
