import pytest
from fastapi import HTTPException

from app.core.deps import get_current_admin
from app.core.security import create_access_token
from app.models.admin_account import AdminAccount, AdminRole


async def test_get_current_admin_valid_token_returns_admin(db):
    admin = AdminAccount(email="deps@test.local", password_hash="x", role=AdminRole.SUPER)
    db.add(admin)
    await db.flush()
    await db.commit()
    token = create_access_token(subject=str(admin.id))
    result = await get_current_admin(token=token, db=db)
    assert result.id == admin.id


async def test_get_current_admin_invalid_token_raises(db):
    with pytest.raises(HTTPException) as exc:
        await get_current_admin(token="bad", db=db)
    assert exc.value.status_code == 401
