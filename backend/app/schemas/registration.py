from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.registration import RegistrationStatus


class RegistrationCreate(BaseModel):
    answers: dict[str, Any]


class RegistrationCreateRequest(BaseModel):
    event_id: UUID
    answers: dict[str, Any]
    slot_id: UUID | None = None


class RegistrationResponse(BaseModel):
    id: UUID
    user_id: UUID
    event_id: UUID
    status: RegistrationStatus
    answers: dict[str, Any]
    waitlist_position: int | None
    checked_in_at: datetime | None
    created_at: datetime
    short_code: str | None = None
    slot_id: UUID | None = None
    notifications_muted: bool = False
    is_late_cancellation: bool = False
    user_first_name: str | None = None
    user_last_name: str | None = None
    user_username: str | None = None

    class Config:
        from_attributes = True
