from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.core.qr import QRService
from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from app.models.event import Event, EventStatus
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User


async def _admin_login(client, db, email: str) -> None:
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    resp = await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})
    assert resp.status_code == 200


def _qr_service() -> QRService:
    settings = get_settings()
    return QRService(
        secret=settings.qr_server_secret,
        bucket_seconds=settings.qr_bucket_seconds,
        fuzz_window=settings.qr_fuzz_window,
    )


# ---------------------------------------------------------------------------
# 1. POST /api/admin/checkin — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkin_happy_path(client, db):
    """Первый чекин: already_checked_in=false, checked_in_at записывается в БД."""
    await _admin_login(client, db, "checkin1@test.com")

    user = User(max_user_id=700010, first_name="Иван", last_name="Петров")
    event = Event(
        title="Checkin Happy Event",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=90,
        status=EventStatus.PUBLISHED,
    )
    db.add_all([user, event])
    await db.commit()

    reg = Registration(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
        answers={},
    )
    db.add(reg)
    await db.commit()

    qr = _qr_service()
    payload = qr.generate(event_id=event.id, reg_id=reg.id, user_id=user.id)

    resp = await client.post("/api/admin/checkin", json={"payload": payload})
    assert resp.status_code == 200
    body = resp.json()
    assert body["already_checked_in"] is False
    assert body["registration_id"] == str(reg.id)
    assert body["event_title"] == "Checkin Happy Event"
    assert body["checked_in_at"] is not None

    await db.refresh(reg)
    assert reg.checked_in_at is not None


# ---------------------------------------------------------------------------
# 2. POST /api/admin/checkin — garbage payload → 422 QR_INVALID
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkin_invalid_payload_returns_422(client, db):
    """Мусорный payload → 422 с деталью QR_INVALID."""
    await _admin_login(client, db, "checkin2@test.com")

    resp = await client.post("/api/admin/checkin", json={"payload": "not-a-real-payload"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "QR_INVALID"


# ---------------------------------------------------------------------------
# 3. POST /api/admin/checkin — second call → already_checked_in=true
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkin_twice_returns_already_checked_in(client, db):
    """Повторный чекин с тем же payload возвращает already_checked_in=true."""
    await _admin_login(client, db, "checkin3@test.com")

    user = User(max_user_id=700020)
    event = Event(
        title="Checkin Twice Event",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=60,
        status=EventStatus.PUBLISHED,
    )
    db.add_all([user, event])
    await db.commit()

    reg = Registration(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
        answers={},
    )
    db.add(reg)
    await db.commit()

    qr = _qr_service()
    payload = qr.generate(event_id=event.id, reg_id=reg.id, user_id=user.id)

    resp1 = await client.post("/api/admin/checkin", json={"payload": payload})
    assert resp1.status_code == 200
    assert resp1.json()["already_checked_in"] is False

    resp2 = await client.post("/api/admin/checkin", json={"payload": payload})
    assert resp2.status_code == 200
    assert resp2.json()["already_checked_in"] is True
