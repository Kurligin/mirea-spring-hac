from datetime import UTC, datetime, timedelta

from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from tests.factories import EventFactory


async def _login(client, db, email):
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})


async def test_put_slots_replaces_all(client, db):
    await _login(client, db, "slot1@test.com")
    e = EventFactory(slots_enabled=True); db.add(e); await db.commit()
    payload = [
        {"starts_at": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(), "duration_minutes": 30, "label": "A"},
        {"starts_at": (datetime.now(UTC) + timedelta(days=1, hours=4)).isoformat(), "duration_minutes": 30, "label": "B", "capacity": 10},
    ]
    resp = await client.put(f"/api/admin/events/{e.id}/slots", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert {s["label"] for s in data} == {"A", "B"}


async def test_get_slots(client, db):
    await _login(client, db, "slot2@test.com")
    e = EventFactory(slots_enabled=True); db.add(e); await db.commit()
    await client.put(
        f"/api/admin/events/{e.id}/slots",
        json=[{"starts_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(), "duration_minutes": 30}],
    )
    resp = await client.get(f"/api/admin/events/{e.id}/slots")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_put_slots_clears_old_then_creates_new(client, db):
    await _login(client, db, "slot3@test.com")
    e = EventFactory(slots_enabled=True); db.add(e); await db.commit()
    await client.put(
        f"/api/admin/events/{e.id}/slots",
        json=[
            {"starts_at": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(), "duration_minutes": 30, "label": "X"},
            {"starts_at": (datetime.now(UTC) + timedelta(days=1, hours=4)).isoformat(), "duration_minutes": 30, "label": "Y"},
        ],
    )
    # Replace with single
    resp = await client.put(
        f"/api/admin/events/{e.id}/slots",
        json=[{"starts_at": (datetime.now(UTC) + timedelta(days=1, hours=6)).isoformat(), "duration_minutes": 30, "label": "Z"}],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["label"] == "Z"


async def test_slots_require_auth(client):
    client.cookies.clear()
    resp = await client.get(f"/api/admin/events/00000000-0000-0000-0000-000000000000/slots")
    assert resp.status_code == 401
