from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from app.models.event import EventStatus
from tests.factories import EventFactory


async def _login(client, db, email):
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})


async def test_dashboard_stats_returns_keys(client, db):
    await _login(client, db, "stats1@test.com")
    resp = await client.get("/api/admin/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "upcoming_events" in data
    assert "confirmed_total" in data
    assert "waitlist_total" in data
    assert "cancelled_week" in data
    assert "active_users" in data


async def test_dashboard_stats_counts_published_upcoming(client, db):
    await _login(client, db, "stats2@test.com")
    db.add(EventFactory(status=EventStatus.PUBLISHED))
    db.add(EventFactory(status=EventStatus.DRAFT))
    await db.commit()
    resp = await client.get("/api/admin/dashboard/stats")
    assert resp.json()["upcoming_events"] >= 1
