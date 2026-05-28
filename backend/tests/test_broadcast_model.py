from datetime import UTC, datetime, timedelta

from app.models.admin_account import AdminAccount, AdminRole
from app.models.broadcast import (
    Broadcast, BroadcastAudience, BroadcastDelivery, BroadcastKind, BroadcastStatus, DeliveryStatus,
)
from app.models.event import Event
from app.models.user import User


async def test_broadcast_persisted(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60)
    admin = AdminAccount(email="b@x.y", password_hash="x", role=AdminRole.SUPER)
    db.add_all([e, admin]); await db.flush()

    b = Broadcast(
        event_id=e.id,
        kind=BroadcastKind.TIME_CHANGE,
        context={"new_time": "2026-05-22T10:00"},
        audience=BroadcastAudience.CONFIRMED,
        status=BroadcastStatus.DRAFT,
        created_by=admin.id,
    )
    db.add(b); await db.flush()
    assert b.id is not None
    assert b.kind == BroadcastKind.TIME_CHANGE
    assert b.status == BroadcastStatus.DRAFT
    assert b.context == {"new_time": "2026-05-22T10:00"}


async def test_broadcast_delivery_persisted(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60)
    admin = AdminAccount(email="bd@x.y", password_hash="x", role=AdminRole.SUPER)
    u = User(max_user_id=66001)
    db.add_all([e, admin, u]); await db.flush()
    b = Broadcast(
        event_id=e.id, kind=BroadcastKind.REMINDER_24H, context={},
        audience=BroadcastAudience.CONFIRMED, status=BroadcastStatus.SENT, created_by=admin.id,
    )
    db.add(b); await db.flush()

    d = BroadcastDelivery(broadcast_id=b.id, user_id=u.id, status=DeliveryStatus.DELIVERED)
    db.add(d); await db.flush()
    assert d.status == DeliveryStatus.DELIVERED
    assert d.error is None
