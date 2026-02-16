from datetime import datetime

from app.schemas.base_schema import BaseSchema


class CandleRead(BaseSchema):
    id: int
    symbol: str
    timeframe: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    dividends: float = 0.0
    stock_splits: float = 0.0
    source: str
    created_at: datetime
