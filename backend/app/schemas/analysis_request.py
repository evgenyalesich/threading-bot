from app.schemas.base_schema import BaseSchema


class AnalysisRequest(BaseSchema):
    symbol: str
    timeframe: str
    lookback_days: int = 120
    strategy: str = "unified_v3"
    h1_timeframe: str = "15m"     # Entry confirmation timeframe
    trend_timeframe: str = "1h"   # Higher-timeframe trend
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
    min_trend_strength: float = 0.12
    min_reward_risk: float = 2.2
    allow_candidate_patterns: bool = True
    quality_mode: str = "balanced"
    require_trend_filter: bool = True
    confluence_tolerance: float | None = None
