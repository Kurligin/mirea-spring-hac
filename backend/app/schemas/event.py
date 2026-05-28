from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.event import EventFormat, EventStatus, EventType, LateCancellationPolicy
from app.schemas.event_field import EventFieldResponse


class EventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    event_type: EventType = EventType.OTHER
    custom_type_label: str | None = Field(default=None, max_length=80)
    format: EventFormat = EventFormat.OFFLINE
    online_url: str | None = Field(default=None, max_length=500)
    late_cancellation_policy: LateCancellationPolicy = LateCancellationPolicy.FORBID
    starts_at: datetime
    duration_minutes: int = Field(..., gt=0)
    location: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    capacity: int | None = Field(default=None, ge=0)
    waitlist_enabled: bool = True
    moderation_required: bool = False
    registration_opens_at: datetime | None = None
    registration_closes_at: datetime | None = None
    cover_media_id: str | None = None
    reminder_offsets_minutes: list[int] = Field(default_factory=list)
    confirmation_template: str | None = None


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    event_type: EventType | None = None
    custom_type_label: str | None = Field(default=None, max_length=80)
    format: EventFormat | None = None
    online_url: str | None = Field(default=None, max_length=500)
    late_cancellation_policy: LateCancellationPolicy | None = None
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    location: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    capacity: int | None = None
    waitlist_enabled: bool | None = None
    moderation_required: bool | None = None
    registration_opens_at: datetime | None = None
    registration_closes_at: datetime | None = None
    cover_media_id: str | None = None
    reminder_offsets_minutes: list[int] | None = None
    confirmation_template: str | None = None


class EventResponse(EventBase):
    id: UUID
    status: EventStatus
    created_at: datetime
    fields: list[EventFieldResponse] = []
    confirmed_count: int | None = None
    waitlist_count: int | None = None

    class Config:
        from_attributes = True
