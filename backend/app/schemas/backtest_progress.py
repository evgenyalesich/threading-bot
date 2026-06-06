from datetime import datetime

from app.schemas.base_schema import BaseSchema


class BacktestProgressRead(BaseSchema):
    status: str = "idle"
    mode: str = "single_pair"
    selected_symbol: str | None = None
    processed_pairs: int = 0
    total_pairs: int = 0
    matched_trades: int = 0
    current_symbol: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None
