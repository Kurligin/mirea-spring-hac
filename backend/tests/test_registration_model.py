from datetime import UTC, datetime, timedelta

from app.models.bot_dialog import BotDialog, DialogState
from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User


async def test_registration_persisted_with_defaults(db):
    user = User(max_user_id=99001)
    event = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60)
    db.add_all([user, event])
    await db.flush()

    reg = Registration(user_id=user.id, event_id=event.id, answers={"full_name": "Иван"})
    db.add(reg)
    await db.flush()
    assert reg.id is not None
    assert reg.status == RegistrationStatus.CONFIRMED
    assert reg.checked_in_at is None
    assert reg.answers == {"full_name": "Иван"}


async def test_bot_dialog_persisted(db):
    user = User(max_user_id=99002)
    event = Event(title="Y", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60)
    db.add_all([user, event])
    await db.flush()

    dlg = BotDialog(
        user_id=user.id,
        event_id=event.id,
        state=DialogState.ASKING_FIELD,
        current_field_index=2,
        answers={"phone": "+7..."},
    )
    db.add(dlg)
    await db.flush()
    assert dlg.id is not None
    assert dlg.state == DialogState.ASKING_FIELD
    assert dlg.current_field_index == 2
