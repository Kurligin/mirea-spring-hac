import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_admin, get_db
from app.core.security import create_access_token, verify_password
from app.models.admin_account import AdminAccount, AdminRole
from app.schemas.auth import AdminResponse, LoginRequest, PinLoginRequest

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])

# Per-email rate-limit для логинов: 5 неудачных попыток за 60 секунд → 429.
# In-memory, без redis — хакатон. Перезагрузка api сбрасывает счётчик.
_FAIL_WINDOW_SEC = 60
_FAIL_MAX = 5
_pin_fails: dict[str, deque[float]] = defaultdict(deque)
_pwd_fails: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(bucket: dict[str, deque[float]], email: str) -> None:
    now = time.monotonic()
    fails = bucket[email]
    while fails and now - fails[0] > _FAIL_WINDOW_SEC:
        fails.popleft()
    if len(fails) >= _FAIL_MAX:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed login attempts, try again later",
        )


def _record_fail(bucket: dict[str, deque[float]], email: str) -> None:
    bucket[email].append(time.monotonic())


def _reset_fails(bucket: dict[str, deque[float]], email: str) -> None:
    bucket.pop(email, None)


# Совместимость с прежним кодом pin-login
def _check_pin_rate_limit(email: str) -> None:
    _check_rate_limit(_pin_fails, email)


def _record_pin_fail(email: str) -> None:
    _record_fail(_pin_fails, email)


def _reset_pin_fails(email: str) -> None:
    _reset_fails(_pin_fails, email)


@router.post("/login", response_model=AdminResponse)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AdminResponse:
    email = payload.email.lower().strip()
    _check_rate_limit(_pwd_fails, email)
    admin = (
        await db.execute(select(AdminAccount).where(AdminAccount.email == payload.email))
    ).scalar_one_or_none()
    if (
        admin is None
        or not admin.is_active
        or not verify_password(payload.password, admin.password_hash)
    ):
        _record_fail(_pwd_fails, email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    _reset_fails(_pwd_fails, email)
    token = create_access_token(subject=str(admin.id), extra={"role": admin.role.value})
    settings = get_settings()
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return AdminResponse(id=admin.id, email=admin.email, role=admin.role, full_name=admin.full_name)


@router.post("/login-pin", response_model=AdminResponse)
async def login_pin(
    payload: PinLoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AdminResponse:
    """Пинкод-логин — только для роли CONTROLLER, у которой задан pin_code_hash."""
    email = payload.email.lower().strip()
    _check_pin_rate_limit(email)
    pin = payload.pin.strip()
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        _record_pin_fail(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    admin = (
        await db.execute(select(AdminAccount).where(AdminAccount.email == payload.email))
    ).scalar_one_or_none()
    if (
        admin is None
        or not admin.is_active
        or admin.role != AdminRole.CONTROLLER
        or admin.pin_code_hash is None
        or not verify_password(pin, admin.pin_code_hash)
    ):
        _record_pin_fail(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    _reset_pin_fails(email)
    token = create_access_token(subject=str(admin.id), extra={"role": admin.role.value})
    settings = get_settings()
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return AdminResponse(id=admin.id, email=admin.email, role=admin.role, full_name=admin.full_name)


@router.get("/me", response_model=AdminResponse)
async def me(admin: AdminAccount = Depends(get_current_admin)) -> AdminResponse:
    return AdminResponse(id=admin.id, email=admin.email, role=admin.role, full_name=admin.full_name)
