from app.schemas.base_schema import BaseSchema


class MarketPairRead(BaseSchema):
    market: str
    symbol: str
    base_asset: str | None
    quote_asset: str | None
    yfinance_symbol: str | None
    last_price: float
    high_price: float
    low_price: float
    price_change_percent: float
    volatility_percent: float
    volatility_score: float
    quote_volume: float
    min_notional: float | None
    min_qty: float | None
    max_qty: float | None
    step_size: float | None
    price_precision: int | None
    quantity_precision: int | None
