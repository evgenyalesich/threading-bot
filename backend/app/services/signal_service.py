from __future__ import annotations

import pandas as pd

from app.models.signal import Signal
from app.repositories.candle_repository import CandleRepository
from app.repositories.signal_repository import SignalRepository
from app.strategies.base_strategy import BaseStrategy
from app.utils.jsonable import to_jsonable
from app.utils.candle_frame import candles_to_df


class SignalService:
    def __init__(
        self,
        candle_repository: CandleRepository,
        signal_repository: SignalRepository,
        strategy: BaseStrategy,
    ) -> None:
        self._candle_repository = candle_repository
        self._signal_repository = signal_repository
        self._strategy = strategy

    async def run(self, symbol: str, timeframe: str, lookback: int = 500) -> Signal | None:
        candles = await self._candle_repository.latest(symbol, timeframe, limit=lookback)
        if not candles:
            return None

        data = candles_to_df(candles)

        signal_payload = self._strategy.evaluate(data)
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
