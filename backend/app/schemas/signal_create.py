from app.schemas.base_schema import BaseSchema


class SignalCreate(BaseSchema):
    symbol: str
    timeframe: str
    signal_type: str
    confidence: float
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    rationale: str | None = None
