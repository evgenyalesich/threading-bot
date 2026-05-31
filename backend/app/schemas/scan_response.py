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


class ScanResponse(BaseSchema):
    status: str
    scanned: int
    new_signals_count: int = 0
    has_new_signals: bool = False
    signals: list[ScanSignalItem]
