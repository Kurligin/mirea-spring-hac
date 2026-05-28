from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventSlotCreate(BaseModel):
    starts_at: datetime
    duration_minutes: int
    capacity: int | None = None
    label: str | None = None


class EventSlotResponse(EventSlotCreate):
    id: UUID
    event_id: UUID

    model_config = ConfigDict(from_attributes=True)
