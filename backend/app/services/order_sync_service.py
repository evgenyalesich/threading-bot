from __future__ import annotations

from datetime import datetime

from app.core.settings import Settings
from app.exchanges.binance_exchange import BinanceExchange
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.services.binance_credentials import resolve_api_credentials


class OrderSyncService:
    def __init__(self, order_repository: OrderRepository, settings: Settings) -> None:
        self._order_repository = order_repository
        self._settings = settings

    async def sync_recent(self, orders: list[Order]) -> list[Order]:
        synced: list[Order] = []
        for order in orders:
            synced.append(await self.sync_one(order))
        return synced

    async def sync_one(self, order: Order) -> Order:
        if order.status in {"closed", "filled", "cancelled"}:
            return order
        if order.market != "futures":
            return order

        trade_env = (order.trade_env or "testnet").lower()
        api_key, api_secret, trade_settings = resolve_api_credentials(self._settings, trade_env, order.market)
        if not api_key or not api_secret:
            return order

        exchange = BinanceExchange(trade_settings)
        try:
            position = await exchange.get_position(order.symbol)
        except Exception:
            return order

        if self._position_amount(position) > 0:
            return order

        exit_price, realized_pnl = await self._latest_exit_snapshot(exchange, order)
        if exit_price is None:
            exit_price = order.exit_price or order.stop_loss or order.take_profit or order.price
        if realized_pnl is None:
            realized_pnl = self._fallback_pnl(order, exit_price)

        return await self._order_repository.update(
            order,
            {
                "status": "closed",
                "exit_price": exit_price,
                "realized_pnl": realized_pnl,
                "closed_at": order.closed_at or datetime.utcnow(),
                "reject_reason": "synced_flat_position",
            },
        )

    def _position_amount(self, position: dict | None) -> float:
        if not isinstance(position, dict):
            return 0.0
        try:
            return abs(float(position.get("positionAmt") or 0.0))
        except (TypeError, ValueError):
            return 0.0

    async def _latest_exit_snapshot(self, exchange: BinanceExchange, order: Order) -> tuple[float | None, float | None]:
        try:
            trades = await exchange.get_account_trades(order.market, order.symbol, limit=50)
        except Exception:
            return None, None
        if not trades:
            return None, None

        order_created_ms = int(order.created_at.timestamp() * 1000) if order.created_at else 0
        relevant = []
        for trade in trades:
            trade_time = trade.get("time")
            try:
                trade_time_int = int(trade_time or 0)
            except (TypeError, ValueError):
                trade_time_int = 0
            if trade_time_int and trade_time_int < order_created_ms:
                continue
            relevant.append(trade)
        if not relevant:
            relevant = trades

        latest = sorted(relevant, key=lambda item: int(item.get("time") or 0))[-1]
        exit_price = self._to_float(latest.get("price"))
        realized_pnl = self._to_float(latest.get("realizedPnl"))
        return exit_price, realized_pnl

    def _fallback_pnl(self, order: Order, exit_price: float | None) -> float | None:
        try:
            entry = float(order.price or 0.0)
            exit_px = float(exit_price or 0.0)
        except (TypeError, ValueError):
            return None
        if entry <= 0 or exit_px <= 0:
            return None
        side = 1 if (order.side or "").upper() == "BUY" else -1
        leverage = int(order.leverage or 1) if order.market == "futures" else 1
        return ((exit_px - entry) / entry) * 100 * side * leverage

    def _to_float(self, value) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result
