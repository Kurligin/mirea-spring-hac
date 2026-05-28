"""Тесты QrSessionManager (sync, без DB) и QrRotationWorker (async, с DB)."""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.bot.qr_rotation import QrRotationWorker, QrSession, QrSessionManager
from app.models.event import Event, EventStatus
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User


# ---------------------------------------------------------------------------
# Вспомогательный контекст-менеджер для подмены session_factory воркера.
# Позволяет передать уже открытую AsyncSession как будто она из фабрики.
# ---------------------------------------------------------------------------

class _SessionCtx:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_):
        pass


def make_factory(db):
    """Возвращает вызываемое, которое отдаёт _SessionCtx(db)."""
    def f():
        return _SessionCtx(db)
    return f


def _mock_client() -> AsyncMock:
    client = AsyncMock()
    client.upload_image_for_attachment = AsyncMock(
        return_value={"type": "image", "payload": {"token": "T"}}
    )
    client.edit_message = AsyncMock(return_value={"ok": True})
    return client


# ===========================================================================
# ЧАСТЬ 1: юнит-тесты QrSessionManager (без DB, sync)
# ===========================================================================


def test_open_registers_and_get_returns_session():
    m = QrSessionManager()
    rid = uuid4()
    s = m.open(reg_id=rid, chat_id=10, message_id="mid", ttl_seconds=900)
    assert s.reg_id == rid
    assert s.chat_id == 10
    assert m.get(rid) is s


def test_open_twice_replaces_previous():
    m = QrSessionManager()
    rid = uuid4()
    m.open(reg_id=rid, chat_id=1, message_id="m1", ttl_seconds=10)
    m.open(reg_id=rid, chat_id=2, message_id="m2", ttl_seconds=10)
    assert m.get(rid).message_id == "m2"
    assert len(m.active()) == 1


def test_stop_removes():
    m = QrSessionManager()
    rid = uuid4()
    m.open(reg_id=rid, chat_id=1, message_id="m", ttl_seconds=10)
    m.stop(rid)
    assert m.get(rid) is None
    assert m.active() == []


def test_stop_nonexistent_is_noop():
    m = QrSessionManager()
    m.stop(uuid4())  # Не должно бросать исключение


def test_active_returns_all_sessions():
    m = QrSessionManager()
    ids = [uuid4() for _ in range(3)]
    for i, rid in enumerate(ids):
        m.open(reg_id=rid, chat_id=i, message_id=f"m{i}", ttl_seconds=10)
    active = m.active()
    assert len(active) == 3
    assert {s.reg_id for s in active} == set(ids)


def test_expires_at_set_correctly():
    m = QrSessionManager()
    rid = uuid4()
    before = time.time()
    s = m.open(reg_id=rid, chat_id=1, message_id="m", ttl_seconds=100)
    after = time.time()
    assert before + 100 <= s.expires_at <= after + 100


def test_last_bucket_default_is_minus_one():
    m = QrSessionManager()
    rid = uuid4()
    s = m.open(reg_id=rid, chat_id=1, message_id="m", ttl_seconds=10)
    assert s.last_bucket == -1


# ===========================================================================
# ЧАСТЬ 2: тесты воркера с DB
# ===========================================================================


@pytest.mark.asyncio
async def test_tick_finalizes_when_checked_in(db):
    """checked_in_at != None → финальная правка с 'отмечены', сессия снята."""
    user = User(max_user_id=800001)
    event = Event(
        title="Worker Test Event 1",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=120,
        status=EventStatus.PUBLISHED,
    )
    db.add_all([user, event])
    await db.commit()

    reg = Registration(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
        answers={},
        checked_in_at=datetime.now(UTC),
    )
    db.add(reg)
    await db.commit()

    client = _mock_client()
    m = QrSessionManager()
    w = QrRotationWorker(client=client, session_factory=make_factory(db), manager=m)
    m.open(reg_id=reg.id, chat_id=1, message_id="mid1", ttl_seconds=900)

    await w._tick()

    client.edit_message.assert_called_once()
    call_kwargs = client.edit_message.call_args.kwargs
    assert "отмечены" in call_kwargs["text"]
    assert call_kwargs["attachments"] == []
    assert m.get(reg.id) is None


@pytest.mark.asyncio
async def test_tick_finalizes_when_ttl_expired(db):
    """TTL истёк → финальная правка с 'истекла', сессия снята."""
    user = User(max_user_id=800002)
    event = Event(
        title="Worker Test Event 2",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=120,
        status=EventStatus.PUBLISHED,
    )
    db.add_all([user, event])
    await db.commit()

    reg = Registration(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
        answers={},
        checked_in_at=None,
    )
    db.add(reg)
    await db.commit()

    client = _mock_client()
    m = QrSessionManager()
    w = QrRotationWorker(client=client, session_factory=make_factory(db), manager=m)
    # TTL = -1 — уже истёк
    m.open(reg_id=reg.id, chat_id=1, message_id="mid2", ttl_seconds=-1)

    await w._tick()

    client.edit_message.assert_called_once()
    call_kwargs = client.edit_message.call_args.kwargs
    assert "истекла" in call_kwargs["text"]
    assert call_kwargs["attachments"] == []
    assert m.get(reg.id) is None


@pytest.mark.asyncio
async def test_tick_rotates_qr_on_bucket_change(db):
    """Смена бакета → edit_message с image-attachment; повторный _tick без смены бакета → нет новой правки."""
    user = User(max_user_id=800003)
    # Событие ещё не завершилось
    event = Event(
        title="Worker Test Event 3",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=120,
        status=EventStatus.PUBLISHED,
    )
    db.add_all([user, event])
    await db.commit()

    reg = Registration(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
        answers={},
        checked_in_at=None,
    )
    db.add(reg)
    await db.commit()

    client = _mock_client()
    m = QrSessionManager()
    w = QrRotationWorker(client=client, session_factory=make_factory(db), manager=m)
    s = m.open(reg_id=reg.id, chat_id=1, message_id="mid3", ttl_seconds=900)

    # Первый тик: last_bucket=-1, текущий бакет != -1 → должен обновить QR
    await w._tick()

    assert client.upload_image_for_attachment.call_count == 1
    assert client.edit_message.call_count == 1
    # Убеждаемся, что вызов был с image-attachment
    edit_kwargs = client.edit_message.call_args.kwargs
    assert edit_kwargs.get("attachments") == [{"type": "image", "payload": {"token": "T"}}]
    assert m.get(reg.id) is not None  # сессия жива

    # Второй тик: бакет не сменился (last_bucket обновлён) → нет новой правки
    await w._tick()

    assert client.upload_image_for_attachment.call_count == 1  # не вызывался повторно
    assert client.edit_message.call_count == 1  # не вызывался повторно
