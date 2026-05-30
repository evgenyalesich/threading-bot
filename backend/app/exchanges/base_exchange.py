from __future__ import annotations


class BaseExchange:
    name = "base"

    async def place_order(self, payload: dict) -> dict:
        raise NotImplementedError

    async def place_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_profit: float,
        stop_loss: float,
    ) -> dict:
        raise NotImplementedError

    async def place_stop_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
        close_position: bool = False,
    ) -> dict:
        raise NotImplementedError

    async def place_take_profit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_profit: float,
        reduce_only: bool = True,
        close_position: bool = False,
    ) -> dict:
        raise NotImplementedError

    async def cancel_order(self, market: str, symbol: str, order_id: str) -> dict:
        raise NotImplementedError

    async def cancel_oco_order(self, symbol: str, order_list_id: str) -> dict:
        raise NotImplementedError

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        raise NotImplementedError

    async def get_position(self, symbol: str) -> dict | None:
        raise NotImplementedError

    async def get_account_trades(self, market: str, symbol: str, limit: int = 50) -> list[dict]:
        raise NotImplementedError
