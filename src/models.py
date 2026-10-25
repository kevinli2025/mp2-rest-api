from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class DatasetInfo(BaseModel):
    id: int
    filename: str
    rows: int
    coumns: int
    column_names: list[str]