from app.schemas.base_schema import BaseSchema


class BackfillRequest(BaseSchema):
    symbol: str
    timeframe: str
    lookback_days: int = 120
    strategy: str = "adaptive_pattern_confluence"
    stride: int = 5
    max_bars: int = 1000
    h1_timeframe: str = "1h"      # Entry signal timeframe (legacy)
    trend_timeframe: str = "4h"   # Trend timeframe (Screen 1)
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
