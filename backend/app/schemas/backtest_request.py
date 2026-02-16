from app.schemas.base_schema import BaseSchema


class BacktestRequest(BaseSchema):
    symbol: str
    timeframe: str
    lookback_days: int = 120
    max_bars: int = 20000
    stride: int = 3
    market: str = "spot"
    data_env: str = "real"
    auto_sync: bool = False
    min_confidence: float = 0.45
    min_confirmations: int = 1
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
