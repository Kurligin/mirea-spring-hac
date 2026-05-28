from uuid import UUID

from pydantic import BaseModel, Field

from app.models.event_field import FieldType


class FieldOptionSchema(BaseModel):
    value: str
    label: str


class FieldValidationSchema(BaseModel):
    pattern: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_value: float | None = None
    max_value: float | None = None


class EventFieldCreate(BaseModel):
    order: int = 0
    key: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    placeholder: str | None = None
    hint: str | None = None
    field_type: FieldType
    required: bool = False
    options: list[FieldOptionSchema] | None = None
    validation: FieldValidationSchema | None = None


class EventFieldResponse(EventFieldCreate):
    id: UUID
    event_id: UUID

    class Config:
        from_attributes = True
