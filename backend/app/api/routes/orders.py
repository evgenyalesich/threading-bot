import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.settings import Settings
from app.exchanges.binance_exchange import BinanceExchange
from app.repositories.order_repository import OrderRepository
from app.schemas.order_create import OrderCreate
from app.schemas.order_read import OrderRead
from app.schemas.order_stop_update import OrderStopUpdate
from app.services.binance_market_service import BinanceMarketService
from app.services.binance_credentials import resolve_api_credentials
from app.services.execution_service import ExecutionService
from app.services.order_sizing_service import OrderSizingService
from app.services.order_sync_service import OrderSyncService
from app.services.telegram_service import TelegramService


router = APIRouter()
settings = Settings()


async def _sync_if_flat(
    order,
    order_repo: OrderRepository,
):
    service = OrderSyncService(order_repo, settings)
    return await service.sync_one(order)


def _to_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _extract_fill_price(response: dict | None, fallback: float | None = None) -> float | None:
    if not isinstance(response, dict):
        return fallback
    for key in ("avgPrice", "price", "stopPrice"):
        price = _to_float(response.get(key))
        if price is not None:
            return price
    fills = response.get("fills")
    if isinstance(fills, list) and fills:
        total_qty = 0.0
        total_quote = 0.0
        for fill in fills:
            price = _to_float(fill.get("price"))
            qty = _to_float(fill.get("qty"))
            if price is None or qty is None:
                continue
            total_qty += qty
            total_quote += price * qty
        if total_qty > 0:
            return total_quote / total_qty
    return fallback


def _order_pnl_pct(order, exit_price: float | None) -> float | None:
    entry = _to_float(order.price)
    if entry is None or exit_price is None:
        return None
    side = 1 if order.side.upper() == "BUY" else -1
    leverage = order.leverage if order.market == "futures" and order.leverage else 1
    return ((exit_price - entry) / entry) * 100 * side * leverage


async def _extract_close_fill_price(
    exchange: BinanceExchange,
    market: str,
    symbol: str,
    response: dict | None,
    fallback: float | None,
) -> float | None:
    response_price = _extract_fill_price(response)
    if response_price is not None:
        return response_price
    order_id = str((response or {}).get("orderId") or "")
    if not order_id:
        return fallback
    for attempt in range(3):
        if attempt:
            await asyncio.sleep(0.15)
        try:
            trades = await exchange.get_account_trades(market, symbol, limit=50)
        except Exception:
            continue
        fills = [trade for trade in trades if str(trade.get("orderId") or "") == order_id]
        total_qty = 0.0
        total_quote = 0.0
        for fill in fills:
            price = _to_float(fill.get("price"))
            qty = _to_float(fill.get("qty") or fill.get("executedQty"))
            if price is None or qty is None:
                continue
            total_qty += qty
            total_quote += price * qty
        if total_qty > 0:
            return total_quote / total_qty
    return fallback


async def _position_is_flat(exchange: BinanceExchange, symbol: str) -> bool:
    try:
        position = await exchange.get_position(symbol)
    except Exception:
        return False
    if not position:
        return True
    amount = _to_float(position.get("positionAmt"))
    if amount is None:
        try:
            amount = abs(float(position.get("positionAmt") or 0))
        except (TypeError, ValueError):
            return False
    return abs(amount) <= 0.0


@router.post("")
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    order_repo = OrderRepository(session)
    trade_env = (payload.trade_env or "testnet").lower()
    market = payload.market.lower()
    api_key, api_secret, trade_settings = resolve_api_credentials(settings, trade_env, market)
    exchange = None
    if api_key and api_secret:
        exchange = BinanceExchange(trade_settings)

    sizing_service = OrderSizingService(BinanceMarketService(trade_settings))
    symbol_normalized = payload.symbol.replace("-", "").upper()

    if payload.auto_quantity or payload.quote_amount is not None:
        if payload.quote_amount is None:
            raise HTTPException(status_code=400, detail="quote_amount_required")
        market_service = BinanceMarketService(trade_settings)
        price = payload.price
        if not price:
            pairs = await market_service.list_pairs(market)
            pair = next((item for item in pairs if item.get("symbol") == symbol_normalized), None)
            price = pair.get("last_price") if pair else None
        sizing = await sizing_service.size_order(
            symbol_normalized,
            market,
            payload.quote_amount,
            price,
            leverage=payload.leverage,
        )
        if sizing.error:
            raise HTTPException(status_code=400, detail=sizing.error)
        payload = payload.model_copy(update={"quantity": sizing.quantity, "price": sizing.price or price})
    else:
        normalized = await sizing_service.normalize_order(
            symbol_normalized,
            market,
            payload.quantity,
            payload.price,
        )
        if normalized.error:
            raise HTTPException(status_code=400, detail=normalized.error)
        payload = payload.model_copy(
            update={
                "quantity": normalized.quantity if normalized.quantity is not None else payload.quantity,
                "price": normalized.price if normalized.price is not None else payload.price,
            }
        )

    # Normalize protective levels to exchange price tick size.
    sl_norm = None
    tp_norm = None
    if payload.stop_loss is not None:
        sl_res = await sizing_service.normalize_order(symbol_normalized, market, None, payload.stop_loss)
        sl_norm = sl_res.price if sl_res.price is not None else payload.stop_loss
    if payload.take_profit is not None:
        tp_res = await sizing_service.normalize_order(symbol_normalized, market, None, payload.take_profit)
        tp_norm = tp_res.price if tp_res.price is not None else payload.take_profit

    take_levels_norm = None
    if payload.take_levels:
        take_levels_norm = []
        for level in payload.take_levels:
            lvl_res = await sizing_service.normalize_order(symbol_normalized, market, None, level)
            take_levels_norm.append(lvl_res.price if lvl_res.price is not None else level)

    payload = payload.model_copy(
        update={
            "stop_loss": sl_norm,
            "take_profit": tp_norm,
            "take_levels": take_levels_norm if take_levels_norm is not None else payload.take_levels,
        }
    )

    service = ExecutionService(order_repo, exchange)
    order = await service.place_order(payload, market=market)
    try:
        await TelegramService(settings).send_message(
            f"Order {order.side} {order.symbol} {order.market}\n"
            f"Status: {order.status}\nEntry: {order.price}\nSL: {order.stop_loss}\nTP: {order.take_profit}"
        )
    except Exception:
        pass
    return OrderRead.model_validate(order)


@router.post("/{order_id}/close")
async def close_order_position(
    order_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    order_repo = OrderRepository(session)
    order = await order_repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status in {"closed", "filled", "cancelled"}:
        return OrderRead.model_validate(order)

    trade_env = (order.trade_env or "testnet").lower()
    api_key, api_secret, trade_settings = resolve_api_credentials(settings, trade_env, order.market)
    if not api_key or not api_secret:
        exit_price = order.exit_price or order.price
        updated = await order_repo.update(
            order,
            {
                "status": "closed",
                "reject_reason": "closed_locally_no_keys",
                "exit_price": exit_price,
                "realized_pnl": _order_pnl_pct(order, exit_price),
                "closed_at": datetime.utcnow(),
            },
        )
        return OrderRead.model_validate(updated)

    exchange = BinanceExchange(trade_settings)
    side = "SELL" if order.side.upper() == "BUY" else "BUY"
    try:
        if order.market == "futures":
            close_response = await exchange.place_order(
                {
                    "market": "futures",
                    "order": {
                        "symbol": order.symbol,
                        "side": side,
                        "type": "MARKET",
                        "quantity": order.quantity,
                        "reduceOnly": True,
                    },
                }
            )
        else:
            close_response = await exchange.place_order(
                {
                    "market": "spot",
                    "order": {
                        "symbol": order.symbol,
                        "side": side,
                        "type": "MARKET",
                        "quantity": order.quantity,
                    },
                }
            )
        exit_price = await _extract_close_fill_price(
            exchange,
            order.market,
            order.symbol,
            close_response,
            fallback=order.exit_price or order.price,
        )
        updated = await order_repo.update(
            order,
            {
                "status": "closed",
                "reject_reason": None,
                "exit_price": exit_price,
                "realized_pnl": _order_pnl_pct(order, exit_price),
                "closed_at": datetime.utcnow(),
            },
        )
    except Exception as exc:
        message = str(exc)
        if order.market == "futures" and "ReduceOnly Order is rejected" in message:
            if await _position_is_flat(exchange, order.symbol):
                exit_price = order.exit_price or order.price
                updated = await order_repo.update(
                    order,
                    {
                        "status": "closed",
                        "reject_reason": "position_already_flat_after_reduce_only_reject",
                        "exit_price": exit_price,
                        "realized_pnl": _order_pnl_pct(order, exit_price),
                        "closed_at": datetime.utcnow(),
                    },
                )
                return OrderRead.model_validate(updated)
        updated = await order_repo.update(order, {"status": "close_failed", "reject_reason": message[:500]})
    try:
        await TelegramService(settings).send_message(
            f"Order closed {updated.symbol}\nStatus: {updated.status}\nExit: {updated.exit_price}\nPnL: {updated.realized_pnl}"
        )
    except Exception:
        pass
    return OrderRead.model_validate(updated)


@router.post("/{order_id}/breakeven")
async def move_to_breakeven(
    order_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    order_repo = OrderRepository(session)
    order = await order_repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.breakeven_moved:
        return OrderRead.model_validate(order)

    entry_price = order.price
    if not entry_price:
        raise HTTPException(status_code=400, detail="entry_price_required")

    trade_env = (order.trade_env or "testnet").lower()
    api_key, api_secret, trade_settings = resolve_api_credentials(settings, trade_env, order.market)
    exchange = None
    if api_key and api_secret:
        exchange = BinanceExchange(trade_settings)

    exit_side = "SELL" if order.side.upper() == "BUY" else "BUY"
    if exchange:
        order = await _sync_if_flat(order, order_repo)
        if order.status == "closed":
            return OrderRead.model_validate(order)
        try:
            if order.market == "spot":
                if order.oco_order_id:
                    await exchange.cancel_oco_order(order.symbol, order.oco_order_id)
                elif order.stop_order_id:
                    await exchange.cancel_order(order.market, order.symbol, order.stop_order_id)
                if order.take_profit:
                    oco = await exchange.place_oco_order(
                        symbol=order.symbol,
                        side=exit_side,
                        quantity=order.quantity,
                        take_profit=order.take_profit,
                        stop_loss=entry_price,
                    )
                    order.oco_order_id = str(oco.get("orderListId") or "")
                    order_reports = oco.get("orderReports") or []
                    for report in order_reports:
                        order_type = report.get("type")
                        if order_type in {"STOP_LOSS_LIMIT", "STOP_LOSS"}:
                            order.stop_order_id = str(report.get("orderId") or "")
                        if order_type in {"LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}:
                            order.take_order_id = str(report.get("orderId") or "")
            else:
                if order.stop_order_id:
                    try:
                        await exchange.cancel_order(order.market, order.symbol, order.stop_order_id)
                    except Exception as exc:
                        # Binance can return -2011 when stop was already canceled/filled.
                        if "-2011" not in str(exc):
                            raise
                stop_order = await exchange.place_stop_order(
                    symbol=order.symbol,
                    side=exit_side,
                    quantity=order.quantity,
                    stop_price=entry_price,
                    reduce_only=True,
                    close_position=True,
                )
                order.stop_order_id = str(stop_order.get("orderId") or "")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"breakeven_failed: {str(exc)[:300]}")

    updated = await order_repo.update(
        order,
        {
            "stop_loss": entry_price,
            "breakeven_moved": True,
        },
    )
    return OrderRead.model_validate(updated)


@router.post("/{order_id}/stop")
async def move_stop(
    order_id: int,
    payload: OrderStopUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    order_repo = OrderRepository(session)
    order = await order_repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    stop_price = payload.price
    if not stop_price or stop_price <= 0:
        raise HTTPException(status_code=400, detail="stop_price_required")

    trade_env = (order.trade_env or "testnet").lower()
    api_key, api_secret, trade_settings = resolve_api_credentials(settings, trade_env, order.market)
    exchange = None
    if api_key and api_secret:
        exchange = BinanceExchange(trade_settings)

    # Normalize stop price to symbol tick size / precision before sending to exchange.
    sizing_service = OrderSizingService(BinanceMarketService(trade_settings))
    symbol_normalized = order.symbol.replace("-", "").upper()
    norm = await sizing_service.normalize_order(symbol_normalized, order.market, None, stop_price)
    if norm.error:
        raise HTTPException(status_code=400, detail=norm.error)
    stop_price = norm.price if norm.price is not None else stop_price

    exit_side = "SELL" if order.side.upper() == "BUY" else "BUY"
    if exchange:
        order = await _sync_if_flat(order, order_repo)
        if order.status == "closed":
            return OrderRead.model_validate(order)
        try:
            if order.market == "spot":
                if order.oco_order_id:
                    await exchange.cancel_oco_order(order.symbol, order.oco_order_id)
                elif order.stop_order_id:
                    await exchange.cancel_order(order.market, order.symbol, order.stop_order_id)
                if order.take_profit:
                    oco = await exchange.place_oco_order(
                        symbol=order.symbol,
                        side=exit_side,
                        quantity=order.quantity,
                        take_profit=order.take_profit,
                        stop_loss=stop_price,
                    )
                    order.oco_order_id = str(oco.get("orderListId") or "")
                    order_reports = oco.get("orderReports") or []
                    for report in order_reports:
                        order_type = report.get("type")
                        if order_type in {"STOP_LOSS_LIMIT", "STOP_LOSS"}:
                            order.stop_order_id = str(report.get("orderId") or "")
                        if order_type in {"LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}:
                            order.take_order_id = str(report.get("orderId") or "")
            else:
                if order.stop_order_id:
                    try:
                        await exchange.cancel_order(order.market, order.symbol, order.stop_order_id)
                    except Exception as exc:
                        # Binance can return -2011 when stop was already canceled/filled.
                        if "-2011" not in str(exc):
                            raise
                stop_order = await exchange.place_stop_order(
                    symbol=order.symbol,
                    side=exit_side,
                    quantity=order.quantity,
                    stop_price=stop_price,
                    reduce_only=True,
                    close_position=True,
                )
                order.stop_order_id = str(stop_order.get("orderId") or "")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"move_stop_failed: {str(exc)[:300]}")

    updated = await order_repo.update(
        order,
        {
            "stop_loss": stop_price,
            "breakeven_moved": True,
        },
    )
    return OrderRead.model_validate(updated)


@router.post("/{order_id}/take")
async def move_take(
    order_id: int,
    payload: OrderStopUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    order_repo = OrderRepository(session)
    order = await order_repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    take_price = payload.price
    if not take_price or take_price <= 0:
        raise HTTPException(status_code=400, detail="take_price_required")

    trade_env = (order.trade_env or "testnet").lower()
    api_key, api_secret, trade_settings = resolve_api_credentials(settings, trade_env, order.market)
    exchange = None
    if api_key and api_secret:
        exchange = BinanceExchange(trade_settings)

    sizing_service = OrderSizingService(BinanceMarketService(trade_settings))
    symbol_normalized = order.symbol.replace("-", "").upper()
    norm = await sizing_service.normalize_order(symbol_normalized, order.market, None, take_price)
    if norm.error:
        raise HTTPException(status_code=400, detail=norm.error)
    take_price = norm.price if norm.price is not None else take_price

    exit_side = "SELL" if order.side.upper() == "BUY" else "BUY"
    if exchange:
        order = await _sync_if_flat(order, order_repo)
        if order.status == "closed":
            return OrderRead.model_validate(order)
        try:
            if order.market == "spot":
                if order.oco_order_id:
                    await exchange.cancel_oco_order(order.symbol, order.oco_order_id)
                elif order.take_order_id:
                    await exchange.cancel_order(order.market, order.symbol, order.take_order_id)
                if order.stop_loss:
                    oco = await exchange.place_oco_order(
                        symbol=order.symbol,
                        side=exit_side,
                        quantity=order.quantity,
                        take_profit=take_price,
                        stop_loss=order.stop_loss,
                    )
                    order.oco_order_id = str(oco.get("orderListId") or "")
                    order_reports = oco.get("orderReports") or []
                    for report in order_reports:
                        order_type = report.get("type")
                        if order_type in {"STOP_LOSS_LIMIT", "STOP_LOSS"}:
                            order.stop_order_id = str(report.get("orderId") or "")
                        if order_type in {"LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}:
                            order.take_order_id = str(report.get("orderId") or "")
            else:
                if order.take_order_id:
                    try:
                        await exchange.cancel_order(order.market, order.symbol, order.take_order_id)
                    except Exception as exc:
                        if "-2011" not in str(exc):
                            raise
                take_order = await exchange.place_take_profit_order(
                    symbol=order.symbol,
                    side=exit_side,
                    quantity=order.quantity,
                    take_profit=take_price,
                    reduce_only=True,
                    close_position=True,
                )
                order.take_order_id = str(take_order.get("orderId") or "")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"move_take_failed: {str(exc)[:300]}")

    updated = await order_repo.update(
        order,
        {
            "take_profit": take_price,
        },
    )
    return OrderRead.model_validate(updated)


@router.get("")
async def list_orders(
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
) -> list[OrderRead]:
    order_repo = OrderRepository(session)
    orders = await order_repo.list_recent(limit=limit)
    orders = await OrderSyncService(order_repo, settings).sync_recent(orders)
    return [OrderRead.model_validate(order) for order in orders]
