from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.core.settings import Settings


class BinanceCandleService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _rest_bases(self, market: str) -> list[str]:
        # Prefer real endpoints for better history coverage; fallback to testnet when needed.
        market = market.lower()
        if market == "futures":
            real_base = self._settings.binance_rest_futures_url.rstrip("/")
            test_base = self._settings.binance_rest_futures_testnet_url.rstrip("/")
        else:
            real_base = self._settings.binance_rest_spot_url.rstrip("/")
            test_base = self._settings.binance_rest_spot_testnet_url.rstrip("/")
        if self._settings.binance_testnet:
            return [real_base, test_base]
        return [real_base]

    def _klines_path(self, market: str) -> str:
        return "/fapi/v1/klines" if market == "futures" else "/api/v3/klines"

    def _interval_ms(self, timeframe: str) -> int | None:
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        if unit == "m":
            return value * 60 * 1000
        if unit == "h":
            return value * 60 * 60 * 1000
        if unit == "d":
            return value * 24 * 60 * 60 * 1000
        return None

    async def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        market: str,
        lookback_days: int,
    ) -> list[list]:
        interval_ms = self._interval_ms(timeframe)
        if not interval_ms:
            return []

        end_time = datetime.now(tz=timezone.utc)
        start_time = end_time - timedelta(days=lookback_days)
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        last_exc: Exception | None = None
        bases = self._rest_bases(market)
        for index, base in enumerate(bases):
            url = f"{base}{self._klines_path(market)}"
            klines: list[list] = []
            current_start = start_ms

            try:
                timeout = httpx.Timeout(20.0, connect=6.0)
                if self._settings.binance_testnet and index == 0 and len(bases) > 1:
                    timeout = httpx.Timeout(6.0, connect=2.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    while current_start < end_ms:
                        params = {
                            "symbol": symbol.upper(),
                            "interval": timeframe,
                            "limit": 1000,
                            "startTime": current_start,
                            "endTime": end_ms,
                        }
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        batch = response.json()
                        if not batch:
                            break
                        klines.extend(batch)
                        last_open = batch[-1][0]
                        next_start = last_open + interval_ms
                        if next_start <= current_start:
                            break
                        current_start = next_start
                return klines
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc:
            raise last_exc
        return []
