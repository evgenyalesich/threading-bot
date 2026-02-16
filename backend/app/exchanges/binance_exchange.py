from __future__ import annotations

import asyncio

from app.core.settings import Settings
from app.exchanges.base_exchange import BaseExchange


class BinanceExchange(BaseExchange):
    name = "binance"

    def _clean_cred(self, value: str | None) -> str | None:
        if not value:
            return None
        v = value.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1].strip()
        return v or None

    def __init__(self, settings: Settings) -> None:
        try:
            from binance.client import Client
        except ImportError as exc:
            raise RuntimeError("python-binance is not installed") from exc

        self._settings = settings
        self._spot_client = None
        self._futures_client = None

        if settings.binance_testnet:
            spot_key = self._clean_cred(settings.binance_spot_testnet_api_key or settings.binance_testnet_api_key)
            spot_secret = self._clean_cred(
                settings.binance_spot_testnet_api_secret or settings.binance_testnet_api_secret
            )
            fut_key = self._clean_cred(
                settings.binance_futures_testnet_api_key or settings.binance_testnet_api_key
            )
            fut_secret = self._clean_cred(
                settings.binance_futures_testnet_api_secret or settings.binance_testnet_api_secret
            )

            if spot_key and spot_secret:
                client = Client(api_key=spot_key, api_secret=spot_secret, testnet=True)
                client.API_URL = settings.binance_rest_spot_testnet_url.rstrip("/") + "/api"
                self._spot_client = client
            if fut_key and fut_secret:
                client = Client(api_key=fut_key, api_secret=fut_secret, testnet=True)
                client.FUTURES_URL = settings.binance_rest_futures_testnet_url.rstrip("/") + "/fapi"
                self._futures_client = client

            if not self._spot_client and not self._futures_client:
                raise ValueError("Binance API credentials are missing")
        else:
            api_key = self._clean_cred(settings.binance_api_key)
            api_secret = self._clean_cred(settings.binance_api_secret)
            if not api_key or not api_secret:
                raise ValueError("Binance API credentials are missing")
            client = Client(api_key=api_key, api_secret=api_secret, testnet=False)
            self._spot_client = client
            self._futures_client = client

    def _client_for(self, market: str):
        market = (market or "spot").lower()
        if market == "futures":
            return self._futures_client or self._spot_client
        return self._spot_client or self._futures_client

    async def place_order(self, payload: dict) -> dict:
        market = payload.get("market", "spot")

        def _place():
            client = self._client_for(market)
            if market == "futures":
                return client.futures_create_order(**payload["order"])
            return client.create_order(**payload["order"])

        return await asyncio.to_thread(_place)

    async def place_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_profit: float,
        stop_loss: float,
    ) -> dict:
        def _place():
            client = self._client_for("spot")
            buffer = 0.001
            if side.upper() == "SELL":
                stop_limit_price = stop_loss * (1 - buffer)
            else:
                stop_limit_price = stop_loss * (1 + buffer)
            return client.create_oco_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=take_profit,
                stopPrice=stop_loss,
                stopLimitPrice=stop_limit_price,
                stopLimitTimeInForce="GTC",
            )

        return await asyncio.to_thread(_place)

    async def place_stop_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
    ) -> dict:
        def _place():
            client = self._client_for("futures")
            return client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP_MARKET",
                stopPrice=stop_price,
                closePosition=False,
                reduceOnly=reduce_only,
                quantity=quantity,
            )

        return await asyncio.to_thread(_place)

    async def place_take_profit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_profit: float,
        reduce_only: bool = True,
    ) -> dict:
        def _place():
            client = self._client_for("futures")
            return client.futures_create_order(
                symbol=symbol,
                side=side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=take_profit,
                closePosition=False,
                reduceOnly=reduce_only,
                quantity=quantity,
            )

        return await asyncio.to_thread(_place)

    async def cancel_order(self, market: str, symbol: str, order_id: str) -> dict:
        def _cancel():
            client = self._client_for(market)
            if market == "futures":
                return client.futures_cancel_order(symbol=symbol, orderId=order_id)
            return client.cancel_order(symbol=symbol, orderId=order_id)

        return await asyncio.to_thread(_cancel)

    async def cancel_oco_order(self, symbol: str, order_list_id: str) -> dict:
        def _cancel():
            client = self._client_for("spot")
            if hasattr(client, "cancel_oco_order"):
                return client.cancel_oco_order(symbol=symbol, orderListId=order_list_id)
            return client.cancel_order(symbol=symbol, orderListId=order_list_id)

        return await asyncio.to_thread(_cancel)

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        def _set():
            client = self._client_for("futures")
            return client.futures_change_leverage(symbol=symbol.upper(), leverage=int(leverage))

        return await asyncio.to_thread(_set)
