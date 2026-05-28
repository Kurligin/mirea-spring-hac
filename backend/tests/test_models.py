from app.models.admin_account import AdminAccount, AdminRole
from app.models.user import User
from app.models.audit_event import AuditEvent


async def test_admin_account_can_be_persisted(db):
    admin = AdminAccount(
        email="admin@mirea.ru",
        password_hash="bcrypt-hash",
        role=AdminRole.SUPER,
        full_name="Иван Иванов",
    )
    db.add(admin)
    await db.flush()
    assert admin.id is not None
    assert admin.role == AdminRole.SUPER


async def test_max_user_can_be_persisted(db):
    user = User(
        max_user_id=12345,
        username="ivan",
        first_name="Иван",
        last_name="Иванов",
    )
    db.add(user)
    await db.flush()
    assert user.id is not None
    assert user.is_active is True
    assert user.is_admin is False


async def test_audit_event_persisted(db):
    ev = AuditEvent(actor_kind="admin", actor_id="11111111-1111-1111-1111-111111111111", action="login")
    db.add(ev)
    await db.flush()
    assert ev.id is not None
