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


router = APIRouter()
settings = Settings()


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

    if payload.auto_quantity or payload.quote_amount is not None:
        if payload.quote_amount is None:
            raise HTTPException(status_code=400, detail="quote_amount_required")
        market_service = BinanceMarketService(trade_settings)
        price = payload.price
        if not price:
            pairs = await market_service.list_pairs(market)
            symbol = payload.symbol.replace("-", "").upper()
            pair = next((item for item in pairs if item.get("symbol") == symbol), None)
            price = pair.get("last_price") if pair else None
        sizing = await OrderSizingService(market_service).size_order(
            payload.symbol.replace("-", "").upper(),
            market,
            payload.quote_amount,
            price,
        )
        if sizing.error:
            raise HTTPException(status_code=400, detail=sizing.error)
        payload = payload.model_copy(update={"quantity": sizing.quantity, "price": price})

    service = ExecutionService(order_repo, exchange)
    order = await service.place_order(payload, market=market)
    return OrderRead.model_validate(order)


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
                await exchange.cancel_order(order.market, order.symbol, order.stop_order_id)
            stop_order = await exchange.place_stop_order(
                symbol=order.symbol,
                side=exit_side,
                quantity=order.quantity,
                stop_price=entry_price,
                reduce_only=True,
            )
            order.stop_order_id = str(stop_order.get("orderId") or "")

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

    exit_side = "SELL" if order.side.upper() == "BUY" else "BUY"
    if exchange:
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
                await exchange.cancel_order(order.market, order.symbol, order.stop_order_id)
            stop_order = await exchange.place_stop_order(
                symbol=order.symbol,
                side=exit_side,
                quantity=order.quantity,
                stop_price=stop_price,
                reduce_only=True,
            )
            order.stop_order_id = str(stop_order.get("orderId") or "")

    updated = await order_repo.update(
        order,
        {
            "stop_loss": stop_price,
            "breakeven_moved": True,
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
    return [OrderRead.model_validate(order) for order in orders]
