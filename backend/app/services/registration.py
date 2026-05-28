from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_time import EventPhase, compute_timing
from app.models.event import Event, LateCancellationPolicy
from app.models.registration import Registration, RegistrationStatus
from app.services.capacity import CapacityService
from app.services.form_field import FormFieldService
from app.services.short_code import generate_short_code


class AlreadyRegistered(Exception):
    pass


class CancelError(Exception):
    """Машино-читаемый код причины — для UI-маппинга в локализованный текст.

    Коды: ALREADY_CHECKED_IN | EVENT_FINISHED | LATE_FORBIDDEN.
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class RegistrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.capacity = CapacityService(db)
        self.form_fields = FormFieldService(db)
        self.last_promoted: Registration | None = None

    async def register(
        self,
        *,
        user_id: UUID,
        event_id: UUID,
        answers: dict[str, Any],
        slot_id: UUID | None = None,
    ) -> Registration:
        # advisory_lock на event_id, чтобы избежать over-booking при гонках
        lock_key = abs(hash(str(event_id))) % (2**31)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:k)").bindparams(k=lock_key))

        existing_stmt = select(Registration).where(
            Registration.user_id == user_id,
            Registration.event_id == event_id,
            Registration.status.in_(
                [RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLIST, RegistrationStatus.PENDING]
            ),
        )
        existing = (await self.db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        validated = await self.form_fields.validate_answers(event_id, answers)
        decision = await self.capacity.decide(event_id, slot_id=slot_id)

        waitlist_pos = None
        if decision == RegistrationStatus.WAITLIST:
            count_stmt = select(func.count(Registration.id)).where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.WAITLIST,
            )
            waitlist_pos = int((await self.db.execute(count_stmt)).scalar() or 0) + 1

        # Генерируем уникальный short_code (retry до 10 попыток)
        short_code = None
        for _ in range(10):
            candidate = generate_short_code()
            exists = (await self.db.execute(
                select(Registration.id).where(Registration.short_code == candidate)
            )).scalar_one_or_none()
            if exists is None:
                short_code = candidate
                break
        if short_code is None:
            raise RuntimeError("Не удалось сгенерировать уникальный short_code за 10 попыток")

        reg = Registration(
            user_id=user_id,
            event_id=event_id,
            slot_id=slot_id,
            status=decision,
            answers=validated,
            waitlist_position=waitlist_pos,
            short_code=short_code,
        )
        self.db.add(reg)
        await self.db.flush()
        return reg

    async def cancel(self, registration_id: UUID) -> Registration:
        reg = (
            await self.db.execute(select(Registration).where(Registration.id == registration_id))
        ).scalar_one_or_none()
        if reg is None:
            raise ValueError(f"Registration {registration_id} not found")

        # Уже отмечен на входе — отмена не имеет смысла и не должна стирать факт прихода.
        if reg.checked_in_at is not None:
            raise CancelError("ALREADY_CHECKED_IN")

        lock_key = abs(hash(str(reg.event_id))) % (2**31)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:k)").bindparams(k=lock_key))

        event = (await self.db.execute(select(Event).where(Event.id == reg.event_id))).scalar_one()
        now = datetime.now(UTC)
        timing = compute_timing(
            starts_at=event.starts_at, duration_minutes=event.duration_minutes, now=now,
        )

        if timing.phase == EventPhase.FINISHED:
            raise CancelError("EVENT_FINISHED")
        if (
            timing.phase == EventPhase.IN_PROGRESS
            and event.late_cancellation_policy == LateCancellationPolicy.FORBID
        ):
            raise CancelError("LATE_FORBIDDEN")

        was_confirmed = reg.status == RegistrationStatus.CONFIRMED
        reg.status = RegistrationStatus.CANCELLED
        reg.cancelled_at = now
        if timing.phase == EventPhase.IN_PROGRESS:
            reg.is_late_cancellation = True
        await self.db.flush()

        if was_confirmed:
            await self._promote_from_waitlist(reg.event_id, slot_id=reg.slot_id)

        return reg

    async def _promote_from_waitlist(self, event_id: UUID, slot_id: UUID | None = None) -> Registration | None:
        stmt = (
            select(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.WAITLIST,
            )
            .order_by(Registration.waitlist_position.asc(), Registration.created_at.asc())
            .limit(1)
        )
        if slot_id is not None:
            stmt = stmt.where(Registration.slot_id == slot_id)
        candidate = (await self.db.execute(stmt)).scalar_one_or_none()
        if candidate is None:
            return None
        candidate.status = RegistrationStatus.CONFIRMED
        candidate.waitlist_position = None
        await self.db.flush()
        self.last_promoted = candidate
        return candidate
