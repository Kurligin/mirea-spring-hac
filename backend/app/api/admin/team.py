from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole
from app.models.user import User
from app.schemas.auth import AdminCreateRequest, AdminResponse, AdminUpdateRequest
from app.services.audit import record_audit

router = APIRouter(prefix="/api/admin/team", tags=["admin-team"])


class WebAdminBrief(BaseModel):
    id: str
    email: str
    role: AdminRole
    full_name: str | None = None
    is_active: bool


class MaxAdminBrief(BaseModel):
    id: str
    max_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    admin_role: AdminRole | None


class TeamResponse(BaseModel):
    web_admins: list[WebAdminBrief]
    max_admins: list[MaxAdminBrief]


class PromoteRequest(BaseModel):
    max_user_id: int
    role: AdminRole = AdminRole.EVENT_MANAGER


class PromoteResponse(BaseModel):
    id: str
    max_user_id: int
    is_admin: bool
    admin_role: AdminRole


@router.get("", response_model=TeamResponse)
async def get_team(
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    web = list((await db.execute(select(AdminAccount))).scalars().all())
    max_admins = list(
        (await db.execute(select(User).where(User.is_admin.is_(True)))).scalars().all()
    )
    return TeamResponse(
        web_admins=[
            WebAdminBrief(
                id=str(a.id),
                email=a.email,
                role=a.role,
                full_name=a.full_name,
                is_active=a.is_active,
            )
            for a in web
        ],
        max_admins=[
            MaxAdminBrief(
                id=str(u.id),
                max_user_id=u.max_user_id,
                username=u.username,
                first_name=u.first_name,
                last_name=u.last_name,
                admin_role=u.admin_role,
            )
            for u in max_admins
        ],
    )


@router.post("", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def create_admin(
    payload: AdminCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    existing = (
        await db.execute(select(AdminAccount).where(AdminAccount.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")

    pin_hash: str | None = None
    if payload.pin_code:
        pin = payload.pin_code.strip()
        if not (pin.isdigit() and 4 <= len(pin) <= 6):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "pin_code must be 4-6 digits",
            )
        pin_hash = hash_password(pin)

    new_admin = AdminAccount(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        full_name=payload.full_name,
        is_active=True,
        pin_code_hash=pin_hash,
    )
    db.add(new_admin)
    await db.flush()
    await record_audit(
        db, admin=_admin, action="admin.create",
        target_kind="admin", target_id=new_admin.id,
        payload={"email": new_admin.email, "role": new_admin.role.value},
    )
    await db.commit()
    return AdminResponse(
        id=new_admin.id,
        email=new_admin.email,
        role=new_admin.role,
        full_name=new_admin.full_name,
    )


def _validate_pin(pin: str) -> str:
    pin = pin.strip()
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "pin_code must be 4-6 digits",
        )
    return pin


@router.patch("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: UUID,
    payload: AdminUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    """Изменить аккаунт: email/role/full_name/is_active/password/pin_code.
    Запреты: не понизить роль последнего SUPER, не отключить самого себя."""
    target = (
        await db.execute(select(AdminAccount).where(AdminAccount.id == admin_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(404, "Admin not found")

    changes: dict[str, object] = {}

    if payload.email and payload.email != target.email:
        dup = (
            await db.execute(
                select(AdminAccount.id).where(
                    AdminAccount.email == payload.email,
                    AdminAccount.id != admin_id,
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
        changes["email"] = (target.email, payload.email)
        target.email = payload.email

    if payload.role is not None and payload.role != target.role:
        # Защита: нельзя понизить последнего активного SUPER
        if target.role == AdminRole.SUPER and payload.role != AdminRole.SUPER:
            other_supers = int((await db.execute(
                select(func.count()).select_from(AdminAccount).where(
                    AdminAccount.role == AdminRole.SUPER,
                    AdminAccount.is_active.is_(True),
                    AdminAccount.id != admin_id,
                )
            )).scalar() or 0)
            if other_supers == 0:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Cannot demote the last active super-admin",
                )
        changes["role"] = (target.role.value, payload.role.value)
        target.role = payload.role

    if payload.full_name is not None and payload.full_name != target.full_name:
        changes["full_name"] = (target.full_name, payload.full_name)
        target.full_name = payload.full_name

    if payload.is_active is not None and payload.is_active != target.is_active:
        if not payload.is_active and target.id == _admin.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cannot deactivate yourself")
        if not payload.is_active and target.role == AdminRole.SUPER:
            other_supers = int((await db.execute(
                select(func.count()).select_from(AdminAccount).where(
                    AdminAccount.role == AdminRole.SUPER,
                    AdminAccount.is_active.is_(True),
                    AdminAccount.id != admin_id,
                )
            )).scalar() or 0)
            if other_supers == 0:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Cannot deactivate the last active super-admin",
                )
        changes["is_active"] = (target.is_active, payload.is_active)
        target.is_active = payload.is_active

    if payload.password:
        if len(payload.password) < 8:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "password must be at least 8 chars")
        target.password_hash = hash_password(payload.password)
        changes["password"] = "changed"

    if payload.pin_code is not None:
        # Пустая строка → сбросить пинкод
        if payload.pin_code == "":
            if target.pin_code_hash is not None:
                target.pin_code_hash = None
                changes["pin_code"] = "cleared"
        else:
            pin = _validate_pin(payload.pin_code)
            target.pin_code_hash = hash_password(pin)
            changes["pin_code"] = "changed"

    if changes:
        await record_audit(
            db, admin=_admin, action="admin.update",
            target_kind="admin", target_id=target.id,
            payload={"changes": {k: (str(v) if not isinstance(v, tuple) else list(v))
                                  for k, v in changes.items()}},
        )
    await db.commit()
    return AdminResponse(
        id=target.id, email=target.email, role=target.role, full_name=target.full_name,
    )


@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin(
    admin_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    """Soft-delete: ставим is_active=False (на admin_accounts ссылается куча FK
    без ondelete — hard-delete небезопасен). Нельзя дезактивировать себя или
    последнего активного SUPER."""
    target = (
        await db.execute(select(AdminAccount).where(AdminAccount.id == admin_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(404, "Admin not found")
    if target.id == _admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot delete yourself")
    if target.role == AdminRole.SUPER and target.is_active:
        other_supers = int((await db.execute(
            select(func.count()).select_from(AdminAccount).where(
                AdminAccount.role == AdminRole.SUPER,
                AdminAccount.is_active.is_(True),
                AdminAccount.id != admin_id,
            )
        )).scalar() or 0)
        if other_supers == 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Cannot delete the last active super-admin",
            )

    target.is_active = False
    await record_audit(
        db, admin=_admin, action="admin.delete",
        target_kind="admin", target_id=admin_id,
        payload={"email": target.email, "role": target.role.value},
    )
    await db.commit()


@router.post("/promote", response_model=PromoteResponse)
async def promote(
    payload: PromoteRequest,
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    user = (
        await db.execute(select(User).where(User.max_user_id == payload.max_user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found in our DB (must interact with bot first)")
    user.is_admin = True
    user.admin_role = payload.role
    await db.commit()
    return PromoteResponse(
        id=str(user.id), max_user_id=user.max_user_id, is_admin=True, admin_role=payload.role
    )
