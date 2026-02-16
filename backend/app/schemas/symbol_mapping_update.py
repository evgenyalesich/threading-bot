from app.schemas.base_schema import BaseSchema


class SymbolMappingUpdate(BaseSchema):
    binance_symbol: str | None = None
    market: str | None = None
