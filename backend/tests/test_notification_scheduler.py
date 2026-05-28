"""Тесты run_tick (планировщик уведомлений): напоминания + рассылки."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.max_client import MaxClient
from app.models.broadcast import Broadcast, BroadcastAudience, BroadcastKind, BroadcastStatus
from app.models.event import Event, EventStatus, EventType
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.scheduler import run_tick
from tests.fixtures.mock_max import create_mock_max_app


# ---------------------------------------------------------------------------
# Общая фикстура: mock MAX client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    app = create_mock_max_app()
    transport = ASGITransport(app=app)
    return MaxClient(token="test-token", base_url="http://mock-max", transport=transport)


# ---------------------------------------------------------------------------
# Тест 1: run_tick создаёт 2 напоминания для опубликованного будущего события,
#          повторный вызов возвращает 0 (идемпотентность).
# ---------------------------------------------------------------------------

async def test_run_tick_creates_reminders_idempotent(test_engine, mock_client):
    """run_tick: 2 напоминания на первом тике, 0 — на повторном (идемпотентность)."""
    SessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as setup:
        event = Event(
            title="Тест напоминаний",
            event_type=EventType.OPEN_DAY,
            status=EventStatus.PUBLISHED,
            starts_at=datetime.now(UTC) + timedelta(days=3),
            duration_minutes=60,
            capacity=50,
            reminder_offsets_minutes=[1440, 60],
        )
        setup.add(event)
        await setup.commit()
        event_id = event.id

    try:
        # Первый тик — минимум 2 напоминания для нашего события
        # (в общем прогоне в БД есть и другие опубликованные события — счётчик глобальный,
        #  точное число для нашего события проверяем запросом ниже).
        result1 = await run_tick(SessionLocal, mock_client)
        assert result1["reminders_created"] >= 2, (
            f"Ожидали минимум 2 напоминания, получили {result1['reminders_created']}"
        )

        # Второй тик — идемпотентен, новых броадкастов нет
        result2 = await run_tick(SessionLocal, mock_client)
        assert result2["reminders_created"] == 0, (
            f"Повторный тик должен вернуть 0, получили {result2['reminders_created']}"
        )

        # Убеждаемся, что в БД именно 2 SCHEDULED-броадкаста для этого события
        async with SessionLocal() as check:
            reminders = (
                await check.execute(
                    select(Broadcast).where(
                        Broadcast.event_id == event_id,
                        Broadcast.status == BroadcastStatus.SCHEDULED,
                    )
                )
            ).scalars().all()
            assert len(reminders) == 2
            offsets = {int(r.context["offset_minutes"]) for r in reminders}
            assert offsets == {1440, 60}
    finally:
        await mock_client.close()


# ---------------------------------------------------------------------------
# Тест 2: run_tick отправляет дозревший SCHEDULED-броадкаст.
# ---------------------------------------------------------------------------

async def test_run_tick_sends_due_broadcast(test_engine, mock_client):
    """run_tick: отправляет броадкаст с send_at в прошлом, статус становится SENT."""
    SessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as setup:
        # Событие в будущем (чтобы оно попало в loop напоминаний, но нас интересует рассылка)
        event = Event(
            title="Тест рассылки",
            event_type=EventType.OPEN_DAY,
            status=EventStatus.PUBLISHED,
            starts_at=datetime.now(UTC) + timedelta(days=10),
            duration_minutes=90,
            capacity=30,
            # Нет reminder_offsets — не хотим, чтобы run_tick создавал лишние броадкасты
            reminder_offsets_minutes=[],
        )
        user = User(max_user_id=999001)
        setup.add_all([event, user])
        await setup.flush()

        reg = Registration(
            user_id=user.id,
            event_id=event.id,
            status=RegistrationStatus.CONFIRMED,
            answers={},
            short_code="TST-0001",
        )
        setup.add(reg)
        await setup.flush()

        # Броадкаст с send_at в прошлом — должен быть отправлен
        broadcast = Broadcast(
            event_id=event.id,
            kind=BroadcastKind.TIME_CHANGE,
            context={},
            audience=BroadcastAudience.CONFIRMED,
            status=BroadcastStatus.SCHEDULED,
            send_at=datetime.now(UTC) - timedelta(minutes=5),
            created_by=None,
        )
        setup.add(broadcast)
        await setup.commit()
        broadcast_id = broadcast.id

    try:
        result = await run_tick(SessionLocal, mock_client)
        assert result["broadcasts_sent"] >= 1, (
            f"Ожидали минимум 1 отправленный броадкаст, получили {result['broadcasts_sent']}"
        )

        # Статус броадкаста должен стать SENT
        async with SessionLocal() as check:
            b = (
                await check.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
            ).scalar_one()
            assert b.status == BroadcastStatus.SENT, (
                f"Ожидали статус SENT, получили {b.status}"
            )
    finally:
        await mock_client.close()
