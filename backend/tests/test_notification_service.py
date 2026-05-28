"""Тесты NotificationService (рассылка броадкастов, напоминания, промоут)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport

from app.core.max_client import MaxClient
from app.models.broadcast import (
    Broadcast,
    BroadcastAudience,
    BroadcastDelivery,
    BroadcastKind,
    BroadcastStatus,
    DeliveryStatus,
)
from app.models.event import Event
from app.models.registration import RegistrationStatus
from app.services.notification import NotificationService
from sqlalchemy import select
from tests.factories import EventFactory, RegistrationFactory, UserFactory
from tests.fixtures.mock_max import create_mock_max_app


@pytest.fixture
def mock_max():
    app = create_mock_max_app()
    transport = ASGITransport(app=app)
    return app, transport


# ---------------------------------------------------------------------------
# Вспомогательные функции для создания тестовых данных
# ---------------------------------------------------------------------------

async def _make_event(db) -> Event:
    event = EventFactory.build(
        starts_at=datetime.now(UTC) + timedelta(days=7),
        reminder_offsets_minutes=[1440, 60],
    )
    db.add(event)
    await db.flush()
    return event


async def _make_broadcast(db, event: Event, **kwargs) -> Broadcast:
    defaults = dict(
        event_id=event.id,
        kind=BroadcastKind.TIME_CHANGE,
        context={},
        audience=BroadcastAudience.CONFIRMED,
        status=BroadcastStatus.DRAFT,
        created_by=None,
    )
    defaults.update(kwargs)
    broadcast = Broadcast(**defaults)
    db.add(broadcast)
    await db.flush()
    return broadcast


# ---------------------------------------------------------------------------
# Тест 1: send_broadcast доставляет 2 подтверждённым участникам
# ---------------------------------------------------------------------------

async def test_send_broadcast_delivers_to_confirmed(db, mock_max):
    mock_app, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)

    event = await _make_event(db)

    user1 = UserFactory.build()
    user2 = UserFactory.build()
    db.add_all([user1, user2])
    await db.flush()

    reg1 = RegistrationFactory.build(
        user_id=user1.id, event_id=event.id, status=RegistrationStatus.CONFIRMED
    )
    reg2 = RegistrationFactory.build(
        user_id=user2.id, event_id=event.id, status=RegistrationStatus.CONFIRMED
    )
    db.add_all([reg1, reg2])
    await db.flush()

    broadcast = await _make_broadcast(db, event)

    svc = NotificationService(db=db, client=client)
    counts = await svc.send_broadcast(broadcast)

    assert counts["delivered"] == 2
    assert counts["muted"] == 0
    assert counts["error"] == 0

    # Проверяем строки BroadcastDelivery
    deliveries = (
        await db.execute(
            select(BroadcastDelivery).where(BroadcastDelivery.broadcast_id == broadcast.id)
        )
    ).scalars().all()
    assert len(deliveries) == 2
    assert all(d.status == DeliveryStatus.DELIVERED for d in deliveries)

    # Броадкаст помечен как SENT
    assert broadcast.status == BroadcastStatus.SENT
    assert broadcast.sent_at is not None

    # MAX принял 2 сообщения
    assert len(mock_app.state.mock["sent_messages"]) >= 2

    await client.close()


# ---------------------------------------------------------------------------
# Тест 2: send_broadcast пропускает registration с notifications_muted=True
# ---------------------------------------------------------------------------

async def test_send_broadcast_skips_muted_registration(db, mock_max):
    _, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)

    event = await _make_event(db)

    user = UserFactory.build()
    db.add(user)
    await db.flush()

    reg = RegistrationFactory.build(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
        notifications_muted=True,
    )
    db.add(reg)
    await db.flush()

    broadcast = await _make_broadcast(db, event)

    svc = NotificationService(db=db, client=client)
    counts = await svc.send_broadcast(broadcast)

    assert counts["muted"] == 1
    assert counts["delivered"] == 0

    delivery = (
        await db.execute(
            select(BroadcastDelivery).where(
                BroadcastDelivery.broadcast_id == broadcast.id,
                BroadcastDelivery.user_id == user.id,
            )
        )
    ).scalar_one()
    assert delivery.status == DeliveryStatus.MUTED

    await client.close()


# ---------------------------------------------------------------------------
# Тест 3: send_broadcast пропускает пользователя с muted_until в будущем
# ---------------------------------------------------------------------------

async def test_send_broadcast_skips_user_muted_until_future(db, mock_max):
    _, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)

    event = await _make_event(db)

    user = UserFactory.build(muted_until=datetime.now(UTC) + timedelta(hours=24))
    db.add(user)
    await db.flush()

    reg = RegistrationFactory.build(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
    )
    db.add(reg)
    await db.flush()

    broadcast = await _make_broadcast(db, event)

    svc = NotificationService(db=db, client=client)
    counts = await svc.send_broadcast(broadcast)

    assert counts["muted"] == 1
    assert counts["delivered"] == 0

    delivery = (
        await db.execute(
            select(BroadcastDelivery).where(
                BroadcastDelivery.broadcast_id == broadcast.id,
                BroadcastDelivery.user_id == user.id,
            )
        )
    ).scalar_one()
    assert delivery.status == DeliveryStatus.MUTED

    await client.close()


# ---------------------------------------------------------------------------
# Тест 4: render для REMINDER_24H содержит «Завтра» и название события
# ---------------------------------------------------------------------------

async def test_render_reminder_24h_contains_zavtra_and_title(db, mock_max):
    _, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)

    event = EventFactory.build(
        title="Открытый день МИРЭА",
        starts_at=datetime.now(UTC) + timedelta(days=3),
        reminder_offsets_minutes=[1440, 60],
    )
    db.add(event)
    await db.flush()

    broadcast = Broadcast(
        event_id=event.id,
        kind=BroadcastKind.REMINDER_24H,
        context={"offset_minutes": 1440},
        audience=BroadcastAudience.CONFIRMED,
        status=BroadcastStatus.SCHEDULED,
        created_by=None,
    )
    db.add(broadcast)
    await db.flush()

    svc = NotificationService(db=db, client=client)
    text = svc.render(broadcast, event)

    assert "Завтра" in text
    assert "Открытый день МИРЭА" in text

    await client.close()


# ---------------------------------------------------------------------------
# Тест 5: create_event_reminders создаёт 2 SCHEDULED-броадкаста, повторный вызов — 0
# ---------------------------------------------------------------------------

async def test_create_event_reminders_idempotent(db, mock_max):
    _, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)

    event = EventFactory.build(
        starts_at=datetime.now(UTC) + timedelta(days=3),
        reminder_offsets_minutes=[1440, 60],
    )
    db.add(event)
    await db.flush()

    svc = NotificationService(db=db, client=client)

    created_first = await svc.create_event_reminders(event)
    assert created_first == 2

    # Проверяем, что оба броадкаста SCHEDULED и created_by=None
    reminders = (
        await db.execute(
            select(Broadcast).where(
                Broadcast.event_id == event.id,
                Broadcast.status == BroadcastStatus.SCHEDULED,
            )
        )
    ).scalars().all()
    assert len(reminders) == 2
    assert all(r.created_by is None for r in reminders)
    assert {int(r.context["offset_minutes"]) for r in reminders} == {1440, 60}

    # Повторный вызов — идемпотентно, 0 новых
    created_second = await svc.create_event_reminders(event)
    assert created_second == 0

    await client.close()
