from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_slot import EventSlot
from app.models.registration import Registration, RegistrationStatus


class SlotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_event(self, event_id: UUID) -> list[EventSlot]:
        stmt = (
            select(EventSlot)
            .where(EventSlot.event_id == event_id)
            .order_by(EventSlot.starts_at)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def replace_all(
        self, event_id: UUID, slots: list[dict[str, Any]]
    ) -> list[EventSlot]:
        """Удалить все текущие слоты event'а и создать новые. Атомарно (в общей транзакции)."""
        existing = await self.list_for_event(event_id)
        for s in existing:
            await self.db.delete(s)
        await self.db.flush()
        result = []
        for s in slots:
            obj = EventSlot(event_id=event_id, **s)
            self.db.add(obj)
            result.append(obj)
        await self.db.flush()
        return result

    async def get(self, slot_id: UUID) -> EventSlot | None:
        stmt = select(EventSlot).where(EventSlot.id == slot_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def remaining_seats(self, slot_id: UUID) -> int | None:
        """None если capacity безлимит, иначе оставшиеся места."""
        slot = await self.get(slot_id)
        if slot is None or slot.capacity is None:
            return None
        confirmed_count = int((
            await self.db.execute(
                select(func.count(Registration.id)).where(
                    Registration.slot_id == slot_id,
                    Registration.status == RegistrationStatus.CONFIRMED,
                )
            )
        ).scalar() or 0)
        return max(0, slot.capacity - confirmed_count)
