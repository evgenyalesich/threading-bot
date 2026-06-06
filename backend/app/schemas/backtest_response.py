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
    max_drawdown_pct: float
    expectancy_pct: float
    sharpe: float | None
    cagr_pct: float | None
    ending_equity: float


class BacktestResponse(BaseSchema):
    status: str
    mode: str = "single_pair"
    selected_symbol: str | None = None
    processed_pairs: int = 0
    universe_pairs: int = 0
    trades: list[BacktestTradeRead]
    stats: BacktestStatsRead
