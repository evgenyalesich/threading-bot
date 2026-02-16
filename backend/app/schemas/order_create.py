from app.schemas.base_schema import BaseSchema


class OrderCreate(BaseSchema):
    exchange: str
    market: str = "spot"
    symbol: str
    side: str
    order_type: str
    quantity: float
    trade_env: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    take_levels: list[float] | None = None
    breakeven_at: float | None = None
    auto_breakeven: bool = False
    attach_orders: bool = True
    quote_amount: float | None = None
    auto_quantity: bool = False
    timeframe: str | None = None
    signal_id: int | None = None
    price: float | None = None
    leverage: int | None = None
