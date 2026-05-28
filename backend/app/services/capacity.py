from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.event_slot import EventSlot
from app.models.registration import Registration, RegistrationStatus


class RegistrationClosed(Exception):
    pass


class EventNotFound(Exception):
    pass


class CapacityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_event(self, event_id: UUID) -> Event:
        event = (await self.db.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        if event is None:
            raise EventNotFound(f"Event {event_id} not found")
        return event

    async def _count_confirmed(self, event_id: UUID) -> int:
        stmt = select(func.count(Registration.id)).where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.CONFIRMED,
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def decide(self, event_id: UUID, slot_id: UUID | None = None) -> RegistrationStatus:
        """Решает: confirmed / waitlist / closed.

        Если event.slots_enabled=True — выбор слота обязателен. capacity берётся со слота
        (если задан), иначе с event'а. Confirmed-счёт считается ТОЛЬКО внутри slot_id.

        Иначе (slots_enabled=False) — старая логика по event.capacity и event-wide счёту.
        """
        event = await self._get_event(event_id)
        now = datetime.now(UTC)
        if event.registration_opens_at and now < event.registration_opens_at:
            raise RegistrationClosed("Регистрация ещё не открыта")
        if event.registration_closes_at and now > event.registration_closes_at:
            raise RegistrationClosed("Регистрация закрыта")

        if event.slots_enabled:
            if slot_id is None:
                raise RegistrationClosed("Не выбран слот")
            slot = (await self.db.execute(
                select(EventSlot).where(EventSlot.id == slot_id, EventSlot.event_id == event_id)
            )).scalar_one_or_none()
            if slot is None:
                raise RegistrationClosed("Слот не найден")
            capacity = slot.capacity if slot.capacity is not None else event.capacity
            if capacity is None:
                return RegistrationStatus.CONFIRMED
            confirmed = int((await self.db.execute(
                select(func.count(Registration.id)).where(
                    Registration.event_id == event_id,
                    Registration.slot_id == slot_id,
                    Registration.status == RegistrationStatus.CONFIRMED,
                )
            )).scalar() or 0)
            if confirmed < capacity:
                return RegistrationStatus.CONFIRMED
            if event.waitlist_enabled:
                return RegistrationStatus.WAITLIST
            raise RegistrationClosed("Места закончились")

        # old path: no slots
        if event.capacity is None:
            return RegistrationStatus.CONFIRMED
        confirmed = await self._count_confirmed(event_id)
        if confirmed < event.capacity:
            return RegistrationStatus.CONFIRMED
        if event.waitlist_enabled:
            return RegistrationStatus.WAITLIST
        raise RegistrationClosed("Места закончились, лист ожидания выключен")

    async def remaining_seats(self, event_id: UUID) -> int | None:
        event = await self._get_event(event_id)
        if event.capacity is None:
            return None
        confirmed = await self._count_confirmed(event_id)
        return max(0, event.capacity - confirmed)
