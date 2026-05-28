from datetime import UTC, datetime, timedelta

from app.models.event import Event, EventStatus
from app.models.event_field import EventField, FieldType


async def test_event_persisted_with_defaults(db):
    event = Event(
        title="День открытых дверей",
        description="Описание",
        starts_at=datetime.now(UTC) + timedelta(days=7),
        duration_minutes=120,
    )
    db.add(event)
    await db.flush()
    assert event.id is not None
    assert event.status == EventStatus.DRAFT
    assert event.capacity is None
    assert event.waitlist_enabled is True


async def test_event_field_persisted(db):
    event = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60)
    db.add(event)
    await db.flush()
    field = EventField(
        event_id=event.id,
        order=0,
        key="full_name",
        label="ФИО",
        field_type=FieldType.TEXT,
        required=True,
    )
    db.add(field)
    await db.flush()
    assert field.id is not None
    assert field.required is True
