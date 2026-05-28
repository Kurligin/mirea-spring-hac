from datetime import UTC, datetime, timedelta

from app.models.event import EventStatus
from app.schemas.event import EventCreate, EventUpdate
from app.services.event import EventService
from tests.factories import EventFactory


async def test_create_event_persists_in_draft(db):
    payload = EventCreate(
        title="Тест",
        starts_at=datetime.now(UTC) + timedelta(days=7),
        duration_minutes=60,
    )
    service = EventService(db)
    event = await service.create(payload)
    assert event.id is not None
    assert event.status == EventStatus.DRAFT


async def test_publish_event_changes_status(db):
    event = EventFactory(status=EventStatus.DRAFT)
    db.add(event)
    await db.flush()

    service = EventService(db)
    result = await service.publish(event.id)
    assert result.status == EventStatus.PUBLISHED


async def test_cancel_event_changes_status(db):
    event = EventFactory(status=EventStatus.PUBLISHED)
    db.add(event)
    await db.flush()

    service = EventService(db)
    result = await service.cancel(event.id)
    assert result.status == EventStatus.CANCELLED


async def test_update_event_changes_fields(db):
    event = EventFactory()
    db.add(event)
    await db.flush()

    service = EventService(db)
    result = await service.update(event.id, EventUpdate(title="New Title", duration_minutes=180))
    assert result.title == "New Title"
    assert result.duration_minutes == 180


async def test_list_events_filters_by_status(db):
    db.add(EventFactory(status=EventStatus.PUBLISHED, title="P1"))
    db.add(EventFactory(status=EventStatus.DRAFT, title="D1"))
    await db.flush()

    service = EventService(db)
    pubs = await service.list(status=EventStatus.PUBLISHED)
    assert all(e.status == EventStatus.PUBLISHED for e in pubs)
