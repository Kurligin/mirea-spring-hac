from collections.abc import AsyncIterator
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.admin_account import AdminAccount


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_admin(
    token: str | None = Cookie(default=None, alias="admin_token"),
    db: AsyncSession = Depends(get_db),
) -> AdminAccount:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(token)
        admin_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from e
    admin = (
        await db.execute(select(AdminAccount).where(AdminAccount.id == admin_id))
    ).scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin not found")
    return admin


async def get_current_max_user(
    authorization: str | None = Header(default=None),
    x_dev_user_id: int | None = Header(default=None, alias="X-Dev-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    """Достаёт MAX-юзера через initData (production) или X-Dev-User-Id (development only).

    Если юзера ещё нет в БД — создаёт его. P5b/P5c будут расширять профиль через бота.
    """
    from app.core.config import get_settings
    from app.core.init_data import InitDataValidator, InvalidInitData
    from app.models.user import User

    settings = get_settings()
    user_id: int | None = None

    if authorization and authorization.startswith("max-webapp "):
        init = authorization.removeprefix("max-webapp ").strip()
        try:
            validator = InitDataValidator(bot_token=settings.max_bot_token)
            parsed = validator.validate(init)
            user_data = parsed.get("user") or {}
            user_id = user_data.get("id")
        except InvalidInitData as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid initData: {e}") from e
    elif x_dev_user_id is not None and settings.environment != "production":
        user_id = int(x_dev_user_id)

    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    user = (
        await db.execute(select(User).where(User.max_user_id == user_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(max_user_id=user_id)
        db.add(user)
        await db.flush()
        await db.commit()
    return user
