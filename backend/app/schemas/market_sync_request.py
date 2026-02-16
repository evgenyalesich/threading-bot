from app.schemas.base_schema import BaseSchema


class MarketSyncRequest(BaseSchema):
    symbol: str
    timeframe: str
    market: str = "spot"
    data_env: str = "real"
    lookback_days: int = 120
    binance_symbol: str | None = None
