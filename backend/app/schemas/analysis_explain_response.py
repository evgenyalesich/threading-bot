from app.schemas.base_schema import BaseSchema


class AnalysisExplainResponse(BaseSchema):
    status: str
    debug: dict

