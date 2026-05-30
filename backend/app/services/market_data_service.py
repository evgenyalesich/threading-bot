from __future__ import annotations

from datetime import datetime, timezone

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
        if not (self._binance_service and binance_symbol and market):
            return 0

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
