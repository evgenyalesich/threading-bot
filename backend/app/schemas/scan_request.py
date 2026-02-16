from app.schemas.base_schema import BaseSchema


class ScanRequest(BaseSchema):
    market: str = "spot"
    timeframe: str = "15m"
    lookback_days: int = 120
    quote: str = "USDT"
    data_env: str = "real"
    min_volatility: float = 0.0
    max_pairs: int = 50
    limit: int = 20
    auto_sync: bool = False
    store_signals: bool = True
    min_confidence: float = 0.5
    min_confirmations: int = 2
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
