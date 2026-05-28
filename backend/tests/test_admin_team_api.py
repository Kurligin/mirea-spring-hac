from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from app.models.user import User


async def _login(client, db, email):
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})


async def test_get_team_returns_web_admins(client, db):
    await _login(client, db, "team1@test.com")
    resp = await client.get("/api/admin/team")
    assert resp.status_code == 200
    body = resp.json()
    assert any(a["email"] == "team1@test.com" for a in body["web_admins"])
    assert "max_admins" in body


async def test_promote_max_user(client, db):
    await _login(client, db, "team2@test.com")
    u = User(max_user_id=555001, username="ivan")
    db.add(u); await db.commit()
    resp = await client.post(
        "/api/admin/team/promote",
        json={"max_user_id": 555001, "role": "event_manager"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True
    assert resp.json()["admin_role"] == "event_manager"


async def test_promote_unknown_user_returns_404(client, db):
    await _login(client, db, "team3@test.com")
    resp = await client.post(
        "/api/admin/team/promote", json={"max_user_id": 999999, "role": "event_manager"}
    )
    assert resp.status_code == 404


async def test_team_requires_auth(client):
    client.cookies.clear()
    resp = await client.get("/api/admin/team")
    assert resp.status_code == 401
