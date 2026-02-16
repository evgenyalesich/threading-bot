from __future__ import annotations

from app.exchanges.base_exchange import BaseExchange
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.schemas.order_create import OrderCreate


class ExecutionService:
    def __init__(self, order_repository: OrderRepository, exchange: BaseExchange | None = None) -> None:
        self._order_repository = order_repository
        self._exchange = exchange

    async def place_order(self, order_create: OrderCreate, market: str | None = None) -> Order:
        resolved_market = market or order_create.market
        resolved_symbol = order_create.symbol.replace("-", "").upper()
        order = Order(
            exchange=order_create.exchange,
            market=resolved_market,
            symbol=resolved_symbol,
            side=order_create.side.upper(),
            order_type=order_create.order_type.upper(),
            quantity=order_create.quantity,
            leverage=order_create.leverage,
            timeframe=order_create.timeframe,
            signal_id=order_create.signal_id,
            price=order_create.price,
            stop_loss=order_create.stop_loss,
            take_profit=order_create.take_profit,
            take_levels=order_create.take_levels,
            breakeven_at=order_create.breakeven_at,
            auto_breakeven=order_create.auto_breakeven,
            trade_env=order_create.trade_env,
            status="new",
        )
        stored = await self._order_repository.add(order)

        if self._exchange is None:
            stored.status = "stored"
            return await self._order_repository.add(stored)

        if resolved_market == "futures" and order_create.leverage and hasattr(self._exchange, "set_leverage"):
            try:
                await self._exchange.set_leverage(resolved_symbol, int(order_create.leverage))
            except Exception:
                # Leverage change can fail due to exchange settings; do not block order placement.
                pass

        payload = {
            "market": resolved_market,
            "order": {
                "symbol": resolved_symbol,
                "side": order_create.side.upper(),
                "type": order_create.order_type.upper(),
                "quantity": order_create.quantity,
            },
        }
        if order_create.price and order_create.order_type.upper() != "MARKET":
            payload["order"]["price"] = order_create.price

        response = await self._exchange.place_order(payload)
        stored.status = "submitted"
        stored.client_order_id = response.get("orderId") or response.get("clientOrderId")
        stored = await self._order_repository.add(stored)

        if (
            order_create.attach_orders
            and (order_create.stop_loss or order_create.take_profit)
            and hasattr(self._exchange, "place_oco_order")
        ):
            exit_side = "SELL" if order_create.side.upper() == "BUY" else "BUY"
            if resolved_market == "spot" and order_create.stop_loss and order_create.take_profit:
                oco = await self._exchange.place_oco_order(
                    symbol=resolved_symbol,
                    side=exit_side,
                    quantity=order_create.quantity,
                    take_profit=order_create.take_profit,
                    stop_loss=order_create.stop_loss,
                )
                stored.oco_order_id = str(oco.get("orderListId") or "")
                order_reports = oco.get("orderReports") or []
                for report in order_reports:
                    order_type = report.get("type")
                    if order_type in {"STOP_LOSS_LIMIT", "STOP_LOSS"}:
                        stored.stop_order_id = str(report.get("orderId") or "")
                    if order_type in {"LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}:
                        stored.take_order_id = str(report.get("orderId") or "")
                return await self._order_repository.add(stored)

            if resolved_market == "futures":
                if order_create.stop_loss:
                    stop_order = await self._exchange.place_stop_order(
                        symbol=resolved_symbol,
                        side=exit_side,
                        quantity=order_create.quantity,
                        stop_price=order_create.stop_loss,
                        reduce_only=True,
                    )
                    stored.stop_order_id = str(stop_order.get("orderId") or "")
                if order_create.take_profit:
                    take_order = await self._exchange.place_take_profit_order(
                        symbol=resolved_symbol,
                        side=exit_side,
                        quantity=order_create.quantity,
                        take_profit=order_create.take_profit,
                        reduce_only=True,
                    )
                    stored.take_order_id = str(take_order.get("orderId") or "")
                return await self._order_repository.add(stored)

        return stored
