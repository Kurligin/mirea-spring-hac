from datetime import UTC, datetime, timedelta

from app.models.bot_dialog import BotDialog, DialogState
from app.models.event import Event, EventStatus, EventType
from app.models.event_slot import EventSlot
from app.models.user import User


async def test_bot_dialog_persists_slot_id(db):
    user = User(max_user_id=900001)
    event = Event(
        title="Слот-событие", event_type=EventType.OPEN_DAY, status=EventStatus.PUBLISHED,
        starts_at=datetime.now(UTC) + timedelta(days=3), duration_minutes=60,
        slots_enabled=True,
    )
    db.add_all([user, event])
    await db.flush()
    slot = EventSlot(
        event_id=event.id, starts_at=datetime.now(UTC) + timedelta(days=3),
        duration_minutes=30, capacity=10, label="10:00",
    )
    db.add(slot)
    await db.flush()

    dialog = BotDialog(
        user_id=user.id, event_id=event.id, state=DialogState.ASKING_FIELD,
        slot_id=slot.id, answers={},
    )
    db.add(dialog)
    await db.flush()
    await db.refresh(dialog)
    assert dialog.slot_id == slot.id


async def test_bot_dialog_slot_id_nullable(db):
    user = User(max_user_id=900002)
    event = Event(
        title="Без слотов", event_type=EventType.OPEN_DAY, status=EventStatus.PUBLISHED,
        starts_at=datetime.now(UTC) + timedelta(days=3), duration_minutes=60,
    )
    db.add_all([user, event])
    await db.flush()
    dialog = BotDialog(user_id=user.id, event_id=event.id, state=DialogState.IDLE, answers={})
    db.add(dialog)
    await db.flush()
    assert dialog.slot_id is None
