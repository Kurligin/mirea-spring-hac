"""Тесты ADMIN API для рассылок (broadcasts)."""
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from tests.factories import EventFactory


async def _login(client, db, email: str) -> None:
    """Создать AdminAccount и выполнить логин — cookie устанавливается в client."""
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    resp = await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})
    assert resp.status_code == 200


async def test_create_broadcast_draft(client, db):
    """POST без send_now/send_at → 201, status == 'draft'."""
    await _login(client, db, "bc1@test.com")
    event = EventFactory()
    db.add(event)
    await db.commit()

    resp = await client.post(
        f"/api/admin/events/{event.id}/broadcasts",
        json={
            "kind": "time_change",
            "audience": "confirmed",
            "extra_text": "Время сдвинулось на час",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["kind"] == "time_change"
    assert data["audience"] == "confirmed"
    assert data["extra_text"] == "Время сдвинулось на час"
    assert data["delivered"] == 0
    assert data["muted"] == 0
    assert data["errors"] == 0


async def test_create_broadcast_send_now_fallback(client, db):
    """POST с send_now=true без bot_client → 201, status == 'scheduled', send_at задан."""
    await _login(client, db, "bc2@test.com")
    event = EventFactory()
    db.add(event)
    await db.commit()

    resp = await client.post(
        f"/api/admin/events/{event.id}/broadcasts",
        json={
            "kind": "venue_change",
            "audience": "all_active",
            "send_now": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    # нет живого MAX-клиента в тестах → fallback: scheduled
    assert data["status"] == "scheduled"
    assert data["send_at"] is not None


async def test_create_broadcast_scheduled(client, db):
    """POST с send_at в будущем → 201, status == 'scheduled'."""
    await _login(client, db, "bc3@test.com")
    event = EventFactory()
    db.add(event)
    await db.commit()

    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    resp = await client.post(
        f"/api/admin/events/{event.id}/broadcasts",
        json={
            "kind": "reminder_24h",
            "audience": "confirmed",
            "send_at": future,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "scheduled"
    assert data["send_at"] is not None


async def test_create_broadcast_event_not_found(client, db):
    """POST к несуществующему event_id → 404."""
    await _login(client, db, "bc4@test.com")
    import uuid

    fake_id = uuid.uuid4()
    resp = await client.post(
        f"/api/admin/events/{fake_id}/broadcasts",
        json={"kind": "link_update"},
    )
    assert resp.status_code == 404


async def test_list_broadcasts_returns_all(client, db):
    """GET после создания 2 рассылок → список длиной 2."""
    await _login(client, db, "bc5@test.com")
    event = EventFactory()
    db.add(event)
    await db.commit()

    for kind in ("time_change", "venue_change"):
        resp = await client.post(
            f"/api/admin/events/{event.id}/broadcasts",
            json={"kind": kind},
        )
        assert resp.status_code == 201

    resp = await client.get(f"/api/admin/events/{event.id}/broadcasts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
