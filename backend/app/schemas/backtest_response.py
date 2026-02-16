from app.schemas.base_schema import BaseSchema


class BacktestTradeRead(BaseSchema):
    id: int
    symbol: str
    timeframe: str
    side: str
    entry: float
    entry_time: int
    confidence: float | None = None
    rationale: str | None = None
    chart_pattern: str | None = None
    candle_bullish: list[str] = []
    candle_bearish: list[str] = []
    trade_plan: dict | None = None
    tp_hits: list[dict] = []
    exit_price: float
    exit_time: int
    exit_reason: str
    pnl: float


class BacktestStatsRead(BaseSchema):
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    profit_factor: float | None
    max_drawdown: float


class BacktestResponse(BaseSchema):
    status: str
    trades: list[BacktestTradeRead]
    stats: BacktestStatsRead
