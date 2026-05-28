from datetime import UTC, datetime, timedelta

from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from app.models.event import EventStatus
from tests.factories import EventFactory


async def _login(client, db, email):
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    resp = await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})
    assert resp.status_code == 200


async def test_create_event_persists_draft(client, db):
    await _login(client, db, "ev1@test.com")
    payload = {
        "title": "Тест",
        "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "duration_minutes": 60,
    }
    resp = await client.post("/api/admin/events", json=payload)
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"


async def test_list_events_filters_by_status(client, db):
    await _login(client, db, "ev2@test.com")
    db.add(EventFactory(title="PubX", status=EventStatus.PUBLISHED))
    db.add(EventFactory(title="DrfX", status=EventStatus.DRAFT))
    await db.commit()
    resp = await client.get("/api/admin/events?status=published")
    assert resp.status_code == 200
    data = resp.json()
    assert all(e["status"] == "published" for e in data)


async def test_publish_changes_status(client, db):
    await _login(client, db, "ev3@test.com")
    e = EventFactory(status=EventStatus.DRAFT)
    db.add(e); await db.commit()
    resp = await client.post(f"/api/admin/events/{e.id}/publish")
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


async def test_cancel_changes_status(client, db):
    await _login(client, db, "ev4@test.com")
    e = EventFactory(status=EventStatus.PUBLISHED)
    db.add(e); await db.commit()
    resp = await client.post(f"/api/admin/events/{e.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_patch_event(client, db):
    await _login(client, db, "ev5@test.com")
    e = EventFactory()
    db.add(e); await db.commit()
    resp = await client.patch(f"/api/admin/events/{e.id}", json={"title": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"


async def test_unauthenticated_returns_401(client):
    # Clear cookie first
    client.cookies.clear()
    resp = await client.get("/api/admin/events")
    assert resp.status_code == 401
