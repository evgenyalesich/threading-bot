from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.core.settings import Settings


@dataclass
class MarketCacheEntry:
    timestamp: datetime
    data: list[dict]


class BinanceMarketService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, MarketCacheEntry] = {}

    def _rest_bases(self, market: str) -> list[str]:
        """Return REST bases to try in order.

        In testnet mode prefer testnet first so automation does not die on
        real-endpoint region blocks like HTTP 418. Fall back to real only if needed.
        """

        market = market.lower()
        if market == "futures":
            real_base = self._settings.binance_rest_futures_url.rstrip("/")
            test_base = self._settings.binance_rest_futures_testnet_url.rstrip("/")
        else:
            real_base = self._settings.binance_rest_spot_url.rstrip("/")
            test_base = self._settings.binance_rest_spot_testnet_url.rstrip("/")

        if self._settings.binance_testnet:
            return [test_base, real_base]
        return [real_base]

    def _exchange_info_path(self, market: str) -> str:
        return "/fapi/v1/exchangeInfo" if market == "futures" else "/api/v3/exchangeInfo"

    def _ticker_path(self, market: str) -> str:
        return "/fapi/v1/ticker/24hr" if market == "futures" else "/api/v3/ticker/24hr"

    async def _fetch_json(self, url: str, timeout: httpx.Timeout) -> dict | list:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    def _derive_yfinance_symbol(self, base_asset: str, quote_asset: str) -> str | None:
        if quote_asset in {"USD", "USDT", "USDC", "BUSD"}:
            return f"{base_asset}-USD"
        return None

    def _extract_min_notional(self, filters: list[dict]) -> float | None:
        for entry in filters:
            if entry.get("filterType") in {"MIN_NOTIONAL", "NOTIONAL"}:
                value = entry.get("minNotional") or entry.get("notional")
                if value is None:
                    continue
                try:
                    return float(value)
                except ValueError:
                    return None
        return None

    def _extract_lot_size(self, filters: list[dict]) -> dict:
        for entry in filters:
            if entry.get("filterType") == "LOT_SIZE":
                try:
                    return {
                        "min_qty": float(entry.get("minQty", 0)),
                        "max_qty": float(entry.get("maxQty", 0)),
                        "step_size": float(entry.get("stepSize", 0)),
                    }
                except (TypeError, ValueError):
                    return {"min_qty": None, "max_qty": None, "step_size": None}
        return {"min_qty": None, "max_qty": None, "step_size": None}

    def _extract_tick_size(self, filters: list[dict]) -> float | None:
        for entry in filters:
            if entry.get("filterType") == "PRICE_FILTER":
                try:
                    return float(entry.get("tickSize", 0) or 0)
                except (TypeError, ValueError):
                    return None
        return None

    def _merge_pairs(self, exchange_info: dict, tickers: list[dict], market: str) -> list[dict]:
        ticker_map = {item["symbol"]: item for item in tickers}
        pairs: list[dict] = []

        for symbol_info in exchange_info.get("symbols", []):
            if symbol_info.get("status") != "TRADING":
                continue
            symbol = symbol_info.get("symbol")
            ticker = ticker_map.get(symbol, {})
            last_price = float(ticker.get("lastPrice", 0) or 0)
            high_price = float(ticker.get("highPrice", last_price) or 0)
            low_price = float(ticker.get("lowPrice", last_price) or 0)
            price_change_percent = float(ticker.get("priceChangePercent", 0) or 0)
            quote_volume = float(ticker.get("quoteVolume", 0) or 0)

            volatility = 0.0
            if last_price > 0:
                volatility = (high_price - low_price) / last_price * 100

            lot_size = self._extract_lot_size(symbol_info.get("filters", []))
            tick_size = self._extract_tick_size(symbol_info.get("filters", []))
            pairs.append(
                {
                    "market": market,
                    "symbol": symbol,
                    "base_asset": symbol_info.get("baseAsset"),
                    "quote_asset": symbol_info.get("quoteAsset"),
                    "yfinance_symbol": self._derive_yfinance_symbol(
                        symbol_info.get("baseAsset"),
                        symbol_info.get("quoteAsset"),
                    ),
                    "last_price": last_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "price_change_percent": price_change_percent,
                    "volatility_percent": volatility,
                    "volatility_score": max(abs(price_change_percent), volatility),
                    "quote_volume": quote_volume,
                    "min_notional": self._extract_min_notional(symbol_info.get("filters", [])),
                    "min_qty": lot_size["min_qty"],
                    "max_qty": lot_size["max_qty"],
                    "step_size": lot_size["step_size"],
                    "tick_size": tick_size,
                    "price_precision": symbol_info.get("pricePrecision"),
                    "quantity_precision": symbol_info.get("quantityPrecision"),
                }
            )

        return pairs

    def _cache_key(self, market: str) -> str:
        return f"pairs::{market}"

    async def list_pairs(self, market: str) -> list[dict]:
        market = market.lower()
        cache_key = self._cache_key(market)
        cached = self._cache.get(cache_key)
        ttl = timedelta(seconds=self._settings.market_cache_ttl)
        if cached and datetime.utcnow() - cached.timestamp < ttl:
            return cached.data

        last_exc: Exception | None = None
        bases = self._rest_bases(market)
        for index, base in enumerate(bases):
            # In testnet mode, first try the testnet endpoint quickly. If it lacks data or
            # fails, fallback to the real endpoint without freezing the worker.
            timeout = httpx.Timeout(20.0, connect=6.0)
            if self._settings.binance_testnet and index == 0 and len(bases) > 1:
                timeout = httpx.Timeout(6.0, connect=2.0)
            try:
                exchange_info = await self._fetch_json(
                    f"{base}{self._exchange_info_path(market)}",
                    timeout=timeout,
                )
                tickers = await self._fetch_json(
                    f"{base}{self._ticker_path(market)}",
                    timeout=timeout,
                )
                pairs = self._merge_pairs(exchange_info, tickers, market)
                self._cache[cache_key] = MarketCacheEntry(timestamp=datetime.utcnow(), data=pairs)
                return pairs
            except Exception as exc:  # httpx errors, bad responses, etc.
                last_exc = exc
                continue

        if last_exc:
            raise last_exc
        return []
