from uuid import UUID
from datetime import datetime,timezone
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, field_serializer

T = TypeVar("T")

class FormatDT():
    @field_serializer("created_at", "updated_at", check_fields=False)
    def _convert_to_ist(self, dt: datetime) -> datetime:
        return dt.replace(tzinfo=timezone.utc).astimezone(tz=None) if dt else None

class CboParams(BaseModel):
    tb: Optional[str] = None
    id_key: Optional[str] = None

class CboItem(BaseModel):
    id: UUID
    name: str

class Response(BaseModel, Generic[T]):
    status: str = "success"
    data: Optional[T] = None
    message: str = ""

class WithoutData(BaseModel):
    status: str = "success"
    message: str = ""

class ErrorRes(BaseModel):
    status: str = "error"
    message: str
    error: str




