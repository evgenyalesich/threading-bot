from app.schemas.base_schema import BaseSchema


class ScanRequest(BaseSchema):
    market: str = "spot"
    timeframe: str = "1h"         # Entry signal timeframe (Screen 2+3)
    lookback_days: int = 120
    strategy: str = "ema200_fib_divergence"
    quote: str = "USDT"
    h1_timeframe: str = "1h"      # Entry signal timeframe (legacy alias)
    trend_timeframe: str = "4h"   # Trend timeframe (Screen 1)
    data_env: str = "real"
    min_volatility: float = 0.0
    max_pairs: int = 50
    limit: int = 20
    auto_sync: bool = False
    store_signals: bool = True
    only_new_signals_minutes: int = 0
    min_confidence: float = 0.35
    min_confirmations: int = 1
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
