from app.schemas.base_schema import BaseSchema


class BackfillRequest(BaseSchema):
    symbol: str
    timeframe: str
    lookback_days: int = 120
    stride: int = 5
    max_bars: int = 1000
    min_confidence: float = 0.5
    min_confirmations: int = 2
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
