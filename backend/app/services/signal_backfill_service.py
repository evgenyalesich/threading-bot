from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.models.signal import Signal
from app.repositories.candle_repository import CandleRepository
from app.repositories.signal_repository import SignalRepository
from app.strategies.base_strategy import BaseStrategy
from app.utils.jsonable import to_jsonable
from app.utils.candle_frame import candles_to_df


class SignalBackfillService:
    def __init__(
        self,
        candle_repository: CandleRepository,
        signal_repository: SignalRepository,
        strategy: BaseStrategy,
    ) -> None:
        self._candle_repository = candle_repository
        self._signal_repository = signal_repository
        self._strategy = strategy

    async def backfill(
        self,
        symbol: str,
        timeframe: str,
        lookback: int,
        stride: int = 5,
        max_bars: int = 1000,
    ) -> int:
        limit = lookback
        if max_bars > 0 and max_bars < lookback:
            limit = max_bars
        min_bars = getattr(self._strategy, "min_bars", 210)
        candles = await self._candle_repository.latest(symbol, timeframe, limit=limit)
        if len(candles) < min_bars:
            return 0

        # MTF: load trend data once before the loop
        h1_data_indexed: pd.DataFrame | None = None
        if getattr(self._strategy, "is_mtf", False):
            trend_tf = getattr(self._strategy, "trend_timeframe", None) or getattr(self._strategy, "h1_timeframe", "1h")
            trend_candles = await self._candle_repository.latest(symbol, trend_tf, limit=5000)
            if trend_candles:
                trend_df = candles_to_df(trend_candles)
                h1_data_indexed = trend_df.set_index("open_time")

        existing_times = await self._signal_repository.list_times(symbol, timeframe)
        known = {time for time in existing_times}

        inserted = 0
        start_index = min_bars
        for index in range(start_index, len(candles), max(stride, 1)):
            window = candles[: index + 1]
            data = candles_to_df(window)
            context: dict | None = None
            if h1_data_indexed is not None:
                last_time = window[-1].open_time
                trend_slice = h1_data_indexed[h1_data_indexed.index <= last_time]
                if len(trend_slice) >= 30:
                    trend_df_slice = trend_slice.reset_index()
                    context = {
                        "trend_data": trend_df_slice,
                        "h1_data": trend_df_slice,  # legacy compat
                        "timeframe": timeframe,
                    }
            elif context is None:
                context = {"timeframe": timeframe}
            signal_payload = self._strategy.evaluate(data, context)
            if not signal_payload:
                continue

            signal_time = window[-1].open_time
            if signal_time in known:
                continue

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
                created_at=signal_time if isinstance(signal_time, datetime) else None,
            )
            await self._signal_repository.add(signal)
            known.add(signal_time)
            inserted += 1

        return inserted
