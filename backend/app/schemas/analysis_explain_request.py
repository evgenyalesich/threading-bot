from app.schemas.base_schema import BaseSchema


class AnalysisExplainRequest(BaseSchema):
    symbol: str
    timeframe: str
    lookback_days: int = 120
    market: str = "spot"
    strategy: str = "ema200_fib_divergence"
    h1_timeframe: str = "1h"
    data_env: str = "real"
    min_confidence: float = 0.35
    min_confirmations: int = 1
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
