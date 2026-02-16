from app.schemas.base_schema import BaseSchema
from app.schemas.signal_read import SignalRead


class ScanSignalItem(BaseSchema):
    symbol: str
    binance_symbol: str
    timeframe: str
    confidence: float
    volatility_score: float
    rank: float
    signal: SignalRead


class ScanResponse(BaseSchema):
    status: str
    scanned: int
    signals: list[ScanSignalItem]
