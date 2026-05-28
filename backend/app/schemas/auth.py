from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.admin_account import AdminRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminCreateRequest(BaseModel):
    email: EmailStr
    password: str
    role: AdminRole = AdminRole.EVENT_MANAGER
    full_name: str | None = None
    pin_code: str | None = None


class AdminUpdateRequest(BaseModel):
    email: EmailStr | None = None
    role: AdminRole | None = None
    full_name: str | None = None
    is_active: bool | None = None
    password: str | None = None
    pin_code: str | None = None


class PinLoginRequest(BaseModel):
    email: EmailStr
    pin: str


class AdminResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: AdminRole
    full_name: str | None = None
