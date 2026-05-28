from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventStatus
from app.models.event_controller import EventController
from app.schemas.event import EventCreate, EventUpdate


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: EventCreate, owner_id: UUID | None = None) -> Event:
        event = Event(**payload.model_dump(), status=EventStatus.DRAFT, owner_id=owner_id)
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event, ["fields"])
        return event

    async def get(self, event_id: UUID) -> Event | None:
        result = await self.db.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        status: EventStatus | None = None,
        limit: int = 100,
        offset: int = 0,
        owner_id: UUID | None = None,
        controller_admin_id: UUID | None = None,
    ) -> list[Event]:
        stmt = select(Event).order_by(Event.starts_at).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(Event.status == status)
        if owner_id is not None:
            stmt = stmt.where(Event.owner_id == owner_id)
        if controller_admin_id is not None:
            stmt = stmt.join(
                EventController,
                (EventController.event_id == Event.id)
                & (EventController.admin_id == controller_admin_id),
            )
        return list((await self.db.execute(stmt)).scalars().all())

    async def update(self, event_id: UUID, payload: EventUpdate) -> Event:
        event = await self.get(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(event, k, v)
        await self.db.flush()
        return event

    async def publish(self, event_id: UUID) -> Event:
        event = await self.get(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")
        event.status = EventStatus.PUBLISHED
        await self.db.flush()
        return event

    async def cancel(self, event_id: UUID) -> Event:
        event = await self.get(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")
        event.status = EventStatus.CANCELLED
        await self.db.flush()
        return event

    async def restore(self, event_id: UUID) -> Event:
        """Возвращает отменённое мероприятие в статус draft для повторного редактирования."""
        event = await self.get(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")
        event.status = EventStatus.DRAFT
        await self.db.flush()
        return event

    async def duplicate(self, event_id: UUID) -> Event:
        """Создаёт копию мероприятия со статусом draft и пометкой '(копия)' в названии."""
        src = await self.get(event_id)
        if src is None:
            raise ValueError(f"Event {event_id} not found")
        copy = Event(
            title=f"{src.title} (копия)",
            description=src.description,
            event_type=src.event_type,
            custom_type_label=src.custom_type_label,
            status=EventStatus.DRAFT,
            starts_at=src.starts_at,
            duration_minutes=src.duration_minutes,
            location=src.location,
            location_lat=src.location_lat,
            location_lng=src.location_lng,
            capacity=src.capacity,
            waitlist_enabled=src.waitlist_enabled,
            moderation_required=src.moderation_required,
            registration_opens_at=src.registration_opens_at,
            registration_closes_at=src.registration_closes_at,
            cover_media_id=src.cover_media_id,
            reminder_offsets_minutes=list(src.reminder_offsets_minutes or []),
            confirmation_template=src.confirmation_template,
        )
        self.db.add(copy)
        await self.db.flush()
        return copy

    async def delete(self, event_id: UUID) -> None:
        """Жёсткое удаление. Разрешено только для draft — для опубликованных используй cancel."""
        event = await self.get(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found")
        if event.status != EventStatus.DRAFT:
            raise ValueError(
                f"Cannot delete event in status {event.status.value};"
                " use cancel for published events"
            )
        await self.db.delete(event)
        await self.db.flush()
