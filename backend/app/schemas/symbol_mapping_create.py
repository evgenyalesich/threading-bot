from app.schemas.base_schema import BaseSchema


class SymbolMappingCreate(BaseSchema):
    yfinance_symbol: str
    binance_symbol: str
    market: str = "spot"
