from app.schemas.base_schema import BaseSchema


class BacktestRequest(BaseSchema):
    symbol: str
    timeframe: str
    lookback_days: int = 120
    max_bars: int = 20000
    stride: int = 3
    market: str = "spot"
    h1_timeframe: str = "1h"      # Entry signal timeframe (Screen 2+3)
    trend_timeframe: str = "4h"   # Trend timeframe (Screen 1)
    data_env: str = "real"
    auto_sync: bool = False
    min_confidence: float = 0.45
    min_confirmations: int = 1
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
    initial_equity: float = 10000.0
    risk_per_trade: float = 0.01
    fee_bps: float = 4.0
    slippage_bps: float = 2.0
    intra_candle_mode: str = "pessimistic"  # pessimistic | optimistic
