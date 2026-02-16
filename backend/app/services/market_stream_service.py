from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import httpx
import websockets

from app.core.settings import Settings


class MarketStreamService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _base_url(self, market: str) -> str:
        if self._settings.binance_testnet:
            # Testnet WS is limited; use real streams for market data.
            if market == "futures":
                return self._settings.binance_ws_futures_url
            return self._settings.binance_ws_spot_url
        if market == "futures":
            return self._settings.binance_ws_futures_url
        return self._settings.binance_ws_spot_url

    def _rest_base(self, market: str) -> str:
        if self._settings.binance_testnet:
            if market == "futures":
                return self._settings.binance_rest_futures_url.rstrip("/")
            return self._settings.binance_rest_spot_url.rstrip("/")
        if market == "futures":
            return self._settings.binance_rest_futures_url.rstrip("/")
        return self._settings.binance_rest_spot_url.rstrip("/")

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

    async def stream_klines(self, symbol: str, timeframe: str, market: str):
        url = f"{self._base_url(market)}/{symbol.lower()}@kline_{timeframe}"
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                async for message in ws:
                    yield json.loads(message)
        except Exception:
            async for payload in self._poll_klines(symbol, timeframe, market):
                yield payload

    def parse_kline(self, payload: dict) -> dict | None:
        if "data" in payload:
            payload = payload["data"]
        kline = payload.get("k")
        if not kline:
            return None
        open_time = datetime.fromtimestamp(kline["t"] / 1000, tz=timezone.utc)
        return {
            "open_time": open_time,
            "open": float(kline["o"]),
            "high": float(kline["h"]),
            "low": float(kline["l"]),
            "close": float(kline["c"]),
            "volume": float(kline["v"]),
            "is_final": bool(kline["x"]),
        }

    async def _poll_klines(self, symbol: str, timeframe: str, market: str):
        interval_ms = self._interval_ms(timeframe)
        if not interval_ms:
            return

        poll_interval = max(2.0, min(10.0, interval_ms / 1000 / 3))
        url = f"{self._rest_base(market)}{self._klines_path(market)}"
        last_open_time = None
        last_close = None

        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                try:
                    response = await client.get(
                        url,
                        params={
                            "symbol": symbol.upper(),
                            "interval": timeframe,
                            "limit": 2,
                        },
                    )
                    response.raise_for_status()
                    batch = response.json()
                except Exception:
                    await asyncio.sleep(poll_interval)
                    continue

                if not batch:
                    await asyncio.sleep(poll_interval)
                    continue

                last = batch[-1]
                open_time_ms = int(last[0])
                now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
                is_final = now_ms >= open_time_ms + interval_ms
                close = float(last[4])

                if last_open_time != open_time_ms or last_close != close or is_final:
                    last_open_time = open_time_ms
                    last_close = close
                    yield {
                        "k": {
                            "t": open_time_ms,
                            "o": str(last[1]),
                            "h": str(last[2]),
                            "l": str(last[3]),
                            "c": str(last[4]),
                            "v": str(last[5]),
                            "x": is_final,
                        }
                    }

                await asyncio.sleep(poll_interval)
