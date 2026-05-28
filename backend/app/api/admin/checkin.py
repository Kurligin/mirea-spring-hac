from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_admin, get_db
from app.core.permissions import assert_can_access_event
from app.core.qr import QRDecodeError, QRExpired, QRService, QRSignatureError
from app.models.admin_account import AdminAccount
from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.checkin_notify import notify_user_checked_in
from app.services.short_code import validate_short_code

router = APIRouter(prefix="/api/admin", tags=["admin-checkin"])


class CheckinRequest(BaseModel):
    payload: str
    event_id: str | None = None


class CheckinResponse(BaseModel):
    registration_id: str
    event_title: str
    user_name: str
    status: str
    short_code: str | None
    checked_in_at: datetime
    already_checked_in: bool


def _user_name(u: User) -> str:
    name = " ".join(p for p in (u.first_name, u.last_name) if p)
    return name or u.username or f"MAX {u.max_user_id}"


@router.post("/checkin", response_model=CheckinResponse)
async def checkin(
    body: CheckinRequest,
    request: Request,
    admin: AdminAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Принять отсканированный payload (short_code или старый QR-токен), отметить приход."""
    payload = (body.payload or "").strip()
    reg: Registration | None = None
    bucket_for_log: int | None = None

    # Сначала пробуем короткий формат XXX-1234 (новый): QR содержит только short_code.
    if validate_short_code(payload.upper()):
        reg = (
            await db.execute(
                select(Registration).where(Registration.short_code == payload.upper())
            )
        ).scalar_one_or_none()

    # Fallback: старый ротирующийся QR-payload (base64-JSON c HMAC).
    if reg is None:
        settings = get_settings()
        qr = QRService(
            secret=settings.qr_server_secret,
            bucket_seconds=settings.qr_bucket_seconds,
            fuzz_window=settings.qr_fuzz_window,
        )
        try:
            parsed = qr.verify(payload)
        except (QRDecodeError, QRSignatureError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="QR_INVALID") from None
        except QRExpired:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="QR_EXPIRED") from None

        reg = (
            await db.execute(select(Registration).where(Registration.id == parsed.reg_id))
        ).scalar_one_or_none()
        bucket_for_log = parsed.bucket

    if reg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registration not found")
    if body.event_id and str(reg.event_id) != body.event_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="FOREIGN_EVENT")

    event = (await db.execute(select(Event).where(Event.id == reg.event_id))).scalar_one_or_none()
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Event not found")
    assert_can_access_event(admin, event)

    if reg.status != RegistrationStatus.CONFIRMED:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="NOT_CONFIRMED")

    reg_user = (await db.execute(select(User).where(User.id == reg.user_id))).scalar_one()

    already = reg.checked_in_at is not None
    if not already:
        reg.checked_in_at = datetime.now(UTC)
        reg.checked_in_by = admin.id
        reg.checked_in_qr_bucket = bucket_for_log
        await db.commit()
        await notify_user_checked_in(request.app.state, user=reg_user, event=event)

    return CheckinResponse(
        registration_id=str(reg.id),
        event_title=event.title,
        user_name=_user_name(reg_user),
        status=reg.status.value,
        short_code=reg.short_code,
        checked_in_at=reg.checked_in_at,
        already_checked_in=already,
    )
