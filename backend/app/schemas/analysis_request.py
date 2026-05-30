from app.schemas.base_schema import BaseSchema


class AnalysisRequest(BaseSchema):
    symbol: str
    timeframe: str
    lookback_days: int = 120
    strategy: str = "ema200_fib_divergence"
    h1_timeframe: str = "1h"      # Entry signal timeframe (Screen 2+3)
    trend_timeframe: str = "4h"   # Trend timeframe (Screen 1)
    market: str = "spot"
    auto_execute: bool = False
    trade_env: str = "testnet"
    order_type: str = "MARKET"
    quantity: float = 0.001
    quote_amount: float | None = None
    auto_quantity: bool = False
    attach_orders: bool = True
    auto_breakeven: bool = True
    leverage: int | None = None
    min_confidence: float = 0.35
    min_confirmations: int = 1
    require_pattern: bool = False
    require_divergence: bool = False
    require_candle: bool = False
    require_volume_confirm: bool = False
