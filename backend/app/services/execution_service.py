from __future__ import annotations

import asyncio
import json

from app.exchanges.base_exchange import BaseExchange
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.schemas.order_create import OrderCreate


class ExecutionService:
    def __init__(self, order_repository: OrderRepository, exchange: BaseExchange | None = None) -> None:
        self._order_repository = order_repository
        self._exchange = exchange

    def _exchange_order_id(self, result: dict) -> str | None:
        raw_id = (
            result.get("orderId")
            or result.get("algoId")
            or result.get("clientOrderId")
            or result.get("clientAlgoId")
        )
        return str(raw_id) if raw_id is not None else None

    async def _place_with_retry(self, fn, label: str, attempts: int = 4, delay_s: float = 0.45) -> dict:
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            try:
                result = await fn()
                order_id = self._exchange_order_id(result) if isinstance(result, dict) else None
                if order_id:
                    return result
                code = result.get("code") if isinstance(result, dict) else None
                msg = result.get("msg") if isinstance(result, dict) else None
                payload = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
                if code is not None or msg:
                    last_error = f"{label}_failed({code}): {msg or payload}"
                else:
                    last_error = f"{label}_failed: missing orderId; payload={payload}"
            except Exception as exc:
                last_error = str(exc)
            if attempt < attempts:
                await asyncio.sleep(delay_s * attempt)
        raise RuntimeError(last_error or f"{label}_failed")

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
            except Exception as exc:
                stored.status = "rejected"
                stored.reject_reason = f"set_leverage_failed: {str(exc)[:450]}"
                return await self._order_repository.add(stored)

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

        try:
            response = await self._exchange.place_order(payload)
            stored.status = "submitted"
            raw_order_id = response.get("orderId") or response.get("clientOrderId")
            stored.client_order_id = str(raw_order_id) if raw_order_id is not None else None
            stored.reject_reason = None
            stored = await self._order_repository.add(stored)
        except Exception as exc:
            stored.status = "rejected"
            stored.reject_reason = str(exc)[:500]
            return await self._order_repository.add(stored)

        if (
            order_create.attach_orders
            and (order_create.stop_loss or order_create.take_profit)
            and hasattr(self._exchange, "place_oco_order")
        ):
            exit_side = "SELL" if order_create.side.upper() == "BUY" else "BUY"
            if (
                resolved_market == "spot"
                and order_create.stop_loss
                and order_create.take_profit
                and order_create.order_type.upper() == "MARKET"
            ):
                try:
                    oco = await self._exchange.place_oco_order(
                        symbol=resolved_symbol,
                        side=exit_side,
                        quantity=order_create.quantity,
                        take_profit=order_create.take_profit,
                        stop_loss=order_create.stop_loss,
                    )
                except Exception as exc:
                    stored.status = "exit_failed"
                    stored.reject_reason = str(exc)[:500]
                    return await self._order_repository.add(stored)
                stored.oco_order_id = str(oco.get("orderListId") or "")
                order_reports = oco.get("orderReports") or []
                for report in order_reports:
                    order_type = report.get("type")
                    if order_type in {"STOP_LOSS_LIMIT", "STOP_LOSS"}:
                        stored.stop_order_id = str(report.get("orderId") or "")
                    if order_type in {"LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}:
                        stored.take_order_id = str(report.get("orderId") or "")
                return await self._order_repository.add(stored)
            if resolved_market == "spot" and order_create.order_type.upper() != "MARKET":
                # For spot LIMIT entries, attaching OCO immediately can fail with insufficient
                # balance because base asset is not filled yet.
                stored.status = "wait_fill"
                return await self._order_repository.add(stored)

            if resolved_market == "futures":
                if order_create.stop_loss:
                    try:
                        stop_order = await self._place_with_retry(
                            lambda: self._exchange.place_stop_order(
                                symbol=resolved_symbol,
                                side=exit_side,
                                quantity=order_create.quantity,
                                stop_price=order_create.stop_loss,
                                reduce_only=True,
                                close_position=True,
                            ),
                            label="stop_order",
                        )
                    except Exception as exc:
                        stored.status = "exit_failed"
                        stored.reject_reason = str(exc)[:500]
                        return await self._order_repository.add(stored)
                    stored.stop_order_id = self._exchange_order_id(stop_order)
                if order_create.take_profit:
                    try:
                        take_order = await self._place_with_retry(
                            lambda: self._exchange.place_take_profit_order(
                                symbol=resolved_symbol,
                                side=exit_side,
                                quantity=order_create.quantity,
                                take_profit=order_create.take_profit,
                                reduce_only=True,
                                close_position=True,
                            ),
                            label="take_order",
                        )
                    except Exception as exc:
                        stored.status = "exit_failed"
                        stored.reject_reason = str(exc)[:500]
                        return await self._order_repository.add(stored)
                    stored.take_order_id = self._exchange_order_id(take_order)
                return await self._order_repository.add(stored)

        return stored
