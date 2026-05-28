from app.core.config import get_settings
from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole


# NOTE: these bytes differ from test_media_service.py to avoid SHA-256 dedup clash
JPEG_BYTES = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606"
    "07060805070707090908"
) + b"\x01" * 1000 + bytes.fromhex("ffd9")


async def _login(client, db, email):
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})


async def test_upload_jpeg_returns_media_response(client, db, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        await _login(client, db, "upl1@test.com")
        files = {"file": ("c.jpg", JPEG_BYTES, "image/jpeg")}
        resp = await client.post("/api/admin/uploads?kind=event_cover", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["mime"].startswith("image/")
        assert data["url"].startswith("/media/")
    finally:
        get_settings.cache_clear()


async def test_upload_rejects_exe(client, db):
    await _login(client, db, "upl2@test.com")
    files = {"file": ("x.exe", b"MZ\x90\x00not-an-image-just-bytes", "application/octet-stream")}
    resp = await client.post("/api/admin/uploads?kind=event_cover", files=files)
    assert resp.status_code == 415


async def test_upload_requires_auth(client):
    client.cookies.clear()
    files = {"file": ("c.jpg", JPEG_BYTES, "image/jpeg")}
    resp = await client.post("/api/admin/uploads?kind=event_cover", files=files)
    assert resp.status_code == 401
