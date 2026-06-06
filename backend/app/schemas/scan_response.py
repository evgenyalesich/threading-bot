from app.schemas.base_schema import BaseSchema
from app.schemas.signal_read import SignalRead


class ScanSignalItem(BaseSchema):
    symbol: str
    binance_symbol: str
    chart_symbol: str
    chart_url: str
    timeframe: str
    confidence: float
    volatility_score: float
    rank: float
    signal: SignalRead


class ScanDiagnosticsRead(BaseSchema):
    total_pairs: int = 0
    eligible_pairs: int = 0
    processed_pairs: int = 0
    matched_signals: int = 0
    reason_counts: dict[str, int] = {}


class ScanResponse(BaseSchema):
    status: str
    mode: str = "market_wide"
    selected_symbol: str | None = None
    processed_pairs: int = 0
    universe_pairs: int = 0
    scanned: int
    new_signals_count: int = 0
    has_new_signals: bool = False
    diagnostics: ScanDiagnosticsRead | None = None
    signals: list[ScanSignalItem]
