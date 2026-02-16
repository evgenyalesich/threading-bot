from app.schemas.base_schema import BaseSchema


class OrderStopUpdate(BaseSchema):
    price: float
