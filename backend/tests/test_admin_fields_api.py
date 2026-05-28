from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from tests.factories import EventFactory


async def _login(client, db, email):
    db.add(AdminAccount(email=email, password_hash=hash_password("p"), role=AdminRole.SUPER))
    await db.commit()
    await client.post("/api/admin/auth/login", json={"email": email, "password": "p"})


async def test_put_fields_replaces_all(client, db):
    await _login(client, db, "fields1@test.com")
    event = EventFactory()
    db.add(event); await db.commit()

    payload = [
        {"key": "full_name", "label": "ФИО", "field_type": "text", "required": True, "order": 0},
        {"key": "email", "label": "Email", "field_type": "email", "required": True, "order": 1},
        {
            "key": "track", "label": "Направление", "field_type": "select", "required": False,
            "order": 2,
            "options": [{"value": "it", "label": "IT"}, {"value": "math", "label": "Математика"}],
        },
    ]
    resp = await client.put(f"/api/admin/events/{event.id}/fields", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[2]["field_type"] == "select"


async def test_get_fields_returns_list(client, db):
    await _login(client, db, "fields2@test.com")
    event = EventFactory()
    db.add(event); await db.commit()

    await client.put(
        f"/api/admin/events/{event.id}/fields",
        json=[{"key": "k", "label": "L", "field_type": "text", "required": False, "order": 0}],
    )
    resp = await client.get(f"/api/admin/events/{event.id}/fields")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_put_replaces_existing(client, db):
    await _login(client, db, "fields3@test.com")
    event = EventFactory()
    db.add(event); await db.commit()

    await client.put(
        f"/api/admin/events/{event.id}/fields",
        json=[
            {"key": "a", "label": "A", "field_type": "text", "required": True, "order": 0},
            {"key": "b", "label": "B", "field_type": "text", "required": True, "order": 1},
        ],
    )
    # Replace with single field
    resp = await client.put(
        f"/api/admin/events/{event.id}/fields",
        json=[{"key": "c", "label": "C", "field_type": "text", "required": True, "order": 0}],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["key"] == "c"
