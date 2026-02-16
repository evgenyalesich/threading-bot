from datetime import datetime

from app.schemas.base_schema import BaseSchema


class SignalRead(BaseSchema):
    id: int
    symbol: str
    timeframe: str
    signal_type: str
    confidence: float
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    meta: dict | None = None
    rationale: str | None
    created_at: datetime
