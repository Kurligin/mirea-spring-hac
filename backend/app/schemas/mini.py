from app.models.event import EventFormat, LateCancellationPolicy
from app.schemas.event import EventResponse
from app.schemas.event_slot import EventSlotResponse


class MiniEventDetailResponse(EventResponse):
    format: EventFormat = EventFormat.OFFLINE
    online_url: str | None = None
    slots_enabled: bool = False
    late_cancellation_policy: LateCancellationPolicy = LateCancellationPolicy.FORBID
    slots: list[EventSlotResponse] = []
