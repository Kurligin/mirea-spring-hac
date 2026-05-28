from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole


async def test_login_with_correct_password_returns_200_and_sets_cookie(client, db):
    db.add(AdminAccount(email="a@b.c", password_hash=hash_password("secret"), role=AdminRole.SUPER))
    await db.commit()

    resp = await client.post("/api/admin/auth/login", json={"email": "a@b.c", "password": "secret"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@b.c"
    assert "admin_token" in resp.cookies


async def test_login_with_wrong_password_returns_401(client, db):
    db.add(AdminAccount(email="b@c.d", password_hash=hash_password("secret"), role=AdminRole.SUPER))
    await db.commit()

    resp = await client.post("/api/admin/auth/login", json={"email": "b@c.d", "password": "wrong"})
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client):
    resp = await client.post("/api/admin/auth/login", json={"email": "x@y.z", "password": "any"})
    assert resp.status_code == 401
