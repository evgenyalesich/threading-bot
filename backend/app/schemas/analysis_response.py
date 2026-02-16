from app.schemas.base_schema import BaseSchema
from app.schemas.order_read import OrderRead
from app.schemas.signal_read import SignalRead


class AnalysisResponse(BaseSchema):
    status: str
    signal: SignalRead | None = None
    order: OrderRead | None = None
    error: str | None = None
