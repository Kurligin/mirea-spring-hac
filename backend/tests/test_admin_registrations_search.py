from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from app.models.registration import Registration, RegistrationStatus
from tests.factories import EventFactory, UserFactory


async def _login(client, db, email):
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})


async def test_search_registrations_by_short_code(client, db):
    await _login(client, db, "regs1@test.com")
    e = EventFactory(); u = UserFactory()
    db.add_all([e, u]); await db.commit()
    db.add(Registration(
        user_id=u.id, event_id=e.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="SRC-1001",
    ))
    await db.commit()

    resp = await client.get(f"/api/admin/events/{e.id}/registrations?q=SRC-1001")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["short_code"] == "SRC-1001"


async def test_search_lowercase_works_too(client, db):
    # ?q=abc-1234 нормализуется в верхний регистр на бэке
    await _login(client, db, "regs2@test.com")
    e = EventFactory(); u = UserFactory()
    db.add_all([e, u]); await db.commit()
    db.add(Registration(
        user_id=u.id, event_id=e.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="XYZ-9999",
    ))
    await db.commit()
    resp = await client.get(f"/api/admin/events/{e.id}/registrations?q=xyz-9999")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_search_no_match_empty(client, db):
    await _login(client, db, "regs3@test.com")
    e = EventFactory(); db.add(e); await db.commit()
    resp = await client.get(f"/api/admin/events/{e.id}/registrations?q=AAA-0000")
    assert resp.status_code == 200
    assert resp.json() == []
