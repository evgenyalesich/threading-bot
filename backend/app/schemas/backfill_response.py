from app.schemas.base_schema import BaseSchema


class BackfillResponse(BaseSchema):
    status: str
    inserted: int
