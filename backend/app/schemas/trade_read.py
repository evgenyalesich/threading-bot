from datetime import datetime

from app.schemas.base_schema import BaseSchema


class TradeRead(BaseSchema):
    id: int
    order_id: int | None
    symbol: str
    side: str
    entry_price: float
    exit_price: float | None
    pnl: float | None
    opened_at: datetime
    closed_at: datetime | None
