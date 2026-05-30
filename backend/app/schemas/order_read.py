from datetime import datetime

from app.schemas.base_schema import BaseSchema


class OrderRead(BaseSchema):
    id: int
    exchange: str
    market: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    leverage: int | None = None
    timeframe: str | None
    signal_id: int | None
    price: float | None
    stop_loss: float | None
    take_profit: float | None
    take_levels: list[float] | None = None
    breakeven_at: float | None
    auto_breakeven: bool
    breakeven_moved: bool
    stop_order_id: str | None
    take_order_id: str | None
    oco_order_id: str | None
    trade_env: str | None
    exit_price: float | None = None
    realized_pnl: float | None = None
    closed_at: datetime | None = None
    status: str
    client_order_id: str | None
    reject_reason: str | None = None
    created_at: datetime
