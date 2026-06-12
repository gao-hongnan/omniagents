"""Response shapes."""

from pydantic import BaseModel


class ReportOut(BaseModel):
    id: int
    body: str
