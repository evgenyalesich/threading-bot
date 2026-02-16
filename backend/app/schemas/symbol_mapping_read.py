from datetime import datetime

from app.schemas.base_schema import BaseSchema


class SymbolMappingRead(BaseSchema):
    id: int
    yfinance_symbol: str
    binance_symbol: str
    market: str
    created_at: datetime
