from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from app.repositories.candle_repository import CandleRepository
from app.services.binance_candle_service import BinanceCandleService


class MarketDataService:
    def __init__(
        self,
        candle_repository: CandleRepository,
        binance_service: BinanceCandleService | None = None,
    ) -> None:
        self._candle_repository = candle_repository
        self._binance_service = binance_service

    async def sync_history(
        self,
        symbol: str,
        timeframe: str,
        lookback_days: int,
        market: str | None = None,
        binance_symbol: str | None = None,
    ) -> int:
        if self._binance_service and binance_symbol and market:
            try:
                records = await self._fetch_binance(
                    symbol=symbol,
                    binance_symbol=binance_symbol,
                    timeframe=timeframe,
                    lookback_days=lookback_days,
                    market=market,
                )
            except Exception:
                return 0
            return await self._candle_repository.upsert_many(records)

        data = await asyncio.to_thread(
            yf.download,
            symbol,
            period=f"{lookback_days}d",
            interval=timeframe,
            auto_adjust=False,
            progress=False,
        )
        if data.empty:
            return 0

        data = data.reset_index()
        timestamp_col = "Datetime" if "Datetime" in data.columns else "Date"
        records: list[dict] = []
        for _, row in data.iterrows():
            ts_value = row[timestamp_col]
            if isinstance(ts_value, pd.Timestamp):
                open_time = ts_value.to_pydatetime()
            elif isinstance(ts_value, datetime):
                open_time = ts_value
            else:
                open_time = datetime.fromisoformat(str(ts_value))
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=timezone.utc)

            records.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open_time": open_time,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0.0)),
                    "source": "yfinance",
                }
            )

        return await self._candle_repository.upsert_many(records)

    async def _fetch_binance(
        self,
        symbol: str,
        binance_symbol: str,
        timeframe: str,
        lookback_days: int,
        market: str,
    ) -> list[dict]:
        klines = await self._binance_service.fetch_klines(
            binance_symbol,
            timeframe,
            market,
            lookback_days,
        )
        records: list[dict] = []
        for entry in klines:
            open_time = datetime.fromtimestamp(entry[0] / 1000, tz=timezone.utc)
            records.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open_time": open_time,
                    "open": float(entry[1]),
                    "high": float(entry[2]),
                    "low": float(entry[3]),
                    "close": float(entry[4]),
                    "volume": float(entry[5]),
                    "source": "binance",
                }
            )
        return records
