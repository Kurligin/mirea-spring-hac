"""Сервис уведомлений: рассылка броадкастов, напоминания, промоут из waitlist."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.max_client import MaxApiError, MaxClient, MaxUserBlocked
from app.models.broadcast import (
    Broadcast,
    BroadcastAudience,
    BroadcastDelivery,
    BroadcastKind,
    BroadcastStatus,
    DeliveryStatus,
)
from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User

_AUDIENCE_STATUSES: dict[BroadcastAudience, list[RegistrationStatus]] = {
    BroadcastAudience.CONFIRMED: [RegistrationStatus.CONFIRMED],
    BroadcastAudience.WAITLIST: [RegistrationStatus.WAITLIST],
    BroadcastAudience.ALL_ACTIVE: [
        RegistrationStatus.CONFIRMED,
        RegistrationStatus.WAITLIST,
        RegistrationStatus.PENDING,
    ],
}

_KIND_PREFIX: dict[BroadcastKind, str] = {
    BroadcastKind.TIME_CHANGE: "⏰ Изменилось время мероприятия",
    BroadcastKind.VENUE_CHANGE: "📍 Изменилось место мероприятия",
    BroadcastKind.LINK_UPDATE: "🔗 Обновлена ссылка мероприятия",
    BroadcastKind.OTHER: "📢 Сообщение по мероприятию",
}


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


class NotificationService:
    """Рассылка уведомлений через MAX с учётом mute и трекингом доставок."""

    def __init__(self, db: AsyncSession, client: MaxClient):
        self.db = db
        self.client = client

    def render(self, broadcast: Broadcast, event: Event) -> str:
        ctx = broadcast.context or {}
        extra = (broadcast.extra_text or "").strip()
        if broadcast.kind in (BroadcastKind.REMINDER_24H, BroadcastKind.REMINDER_1H):
            offset = int(ctx.get("offset_minutes", 0))
            lead = "Завтра" if offset >= 1440 else "Через час" if offset >= 60 else "Скоро"
            lines = [f"🔔 {lead} — «{event.title}»", f"Когда: {_fmt_dt(event.starts_at)}"]
            if event.location:
                lines.append(f"Где: {event.location}")
            lines.append("Ждём вас!")
            return "\n".join(lines)
        prefix = _KIND_PREFIX.get(broadcast.kind, "📢 Сообщение по мероприятию")
        if broadcast.kind == BroadcastKind.OTHER and broadcast.custom_topic_label:
            prefix = f"📢 {broadcast.custom_topic_label}"
        lines = [f"{prefix} «{event.title}»."]
        if extra:
            lines.append(extra)
        return "\n".join(lines)

    async def _recipients(self, broadcast: Broadcast) -> list[tuple[Registration, User]]:
        statuses = _AUDIENCE_STATUSES[broadcast.audience]
        stmt = (
            select(Registration, User)
            .join(User, User.id == Registration.user_id)
            .where(
                Registration.event_id == broadcast.event_id,
                Registration.status.in_(statuses),
            )
        )
        return list((await self.db.execute(stmt)).all())

    async def _upsert_delivery(
        self,
        broadcast_id,
        user_id,
        status: DeliveryStatus,
        error: str | None = None,
    ) -> None:
        existing = (
            await self.db.execute(
                select(BroadcastDelivery).where(
                    BroadcastDelivery.broadcast_id == broadcast_id,
                    BroadcastDelivery.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = BroadcastDelivery(broadcast_id=broadcast_id, user_id=user_id)
            self.db.add(existing)
        existing.status = status
        existing.error = error
        if status == DeliveryStatus.DELIVERED:
            existing.sent_at = datetime.now(UTC)

    async def send_broadcast(self, broadcast: Broadcast) -> dict[str, int]:
        """Разослать броадкаст аудитории. Возвращает счётчики доставок."""
        event = (
            await self.db.execute(select(Event).where(Event.id == broadcast.event_id))
        ).scalar_one()
        text = self.render(broadcast, event)
        broadcast.status = BroadcastStatus.SENDING
        await self.db.flush()

        now = datetime.now(UTC)
        counts = {"delivered": 0, "muted": 0, "error": 0}
        for reg, user in await self._recipients(broadcast):
            if not user.is_active:
                await self._upsert_delivery(
                    broadcast.id, user.id, DeliveryStatus.ERROR, "user inactive"
                )
                counts["error"] += 1
                continue
            if user.muted_until is not None and user.muted_until > now:
                await self._upsert_delivery(broadcast.id, user.id, DeliveryStatus.MUTED)
                counts["muted"] += 1
                continue
            if reg.notifications_muted:
                await self._upsert_delivery(broadcast.id, user.id, DeliveryStatus.MUTED)
                counts["muted"] += 1
                continue
            try:
                await self.client.send_message(user_id=user.max_user_id, text=text)
            except MaxUserBlocked:
                user.is_active = False
                await self._upsert_delivery(
                    broadcast.id, user.id, DeliveryStatus.ERROR, "bot blocked"
                )
                counts["error"] += 1
            except MaxApiError as e:
                await self._upsert_delivery(
                    broadcast.id, user.id, DeliveryStatus.ERROR, str(e)[:200]
                )
                counts["error"] += 1
            else:
                await self._upsert_delivery(broadcast.id, user.id, DeliveryStatus.DELIVERED)
                counts["delivered"] += 1

        broadcast.status = BroadcastStatus.SENT
        broadcast.sent_at = datetime.now(UTC)
        await self.db.flush()
        return counts

    async def notify_promotion(self, registration: Registration) -> None:
        """DM юзеру: место освободилось, он переведён из листа ожидания в подтверждённые."""
        user = (
            await self.db.execute(select(User).where(User.id == registration.user_id))
        ).scalar_one_or_none()
        event = (
            await self.db.execute(select(Event).where(Event.id == registration.event_id))
        ).scalar_one_or_none()
        if user is None or event is None or not user.is_active:
            return
        if user.muted_until is not None and user.muted_until > datetime.now(UTC):
            return
        if registration.notifications_muted:
            return
        text = (
            f"🎉 Освободилось место на «{event.title}»!\n"
            f"Вы переведены из листа ожидания — запись подтверждена.\n"
            f"Когда: {_fmt_dt(event.starts_at)}"
        )
        try:
            await self.client.send_message(user_id=user.max_user_id, text=text)
        except MaxApiError:
            pass

    async def create_event_reminders(self, event: Event) -> int:
        """Создаёт SCHEDULED-броадкасты-напоминания для будущих offset'ов события.

        Идемпотентно: повторный вызов не дублирует уже созданные напоминания.
        Возвращает число созданных броадкастов.
        """
        now = datetime.now(UTC)
        existing = (
            await self.db.execute(
                select(Broadcast).where(
                    Broadcast.event_id == event.id,
                    Broadcast.kind.in_(
                        [BroadcastKind.REMINDER_24H, BroadcastKind.REMINDER_1H]
                    ),
                )
            )
        ).scalars().all()
        existing_offsets = {
            int((b.context or {}).get("offset_minutes", -1)) for b in existing
        }
        created = 0
        for raw_offset in event.reminder_offsets_minutes or []:
            offset = int(raw_offset)
            if offset in existing_offsets:
                continue
            send_at = event.starts_at - timedelta(minutes=offset)
            if send_at <= now:
                continue
            kind = BroadcastKind.REMINDER_24H if offset >= 1440 else BroadcastKind.REMINDER_1H
            self.db.add(
                Broadcast(
                    event_id=event.id,
                    kind=kind,
                    audience=BroadcastAudience.CONFIRMED,
                    status=BroadcastStatus.SCHEDULED,
                    send_at=send_at,
                    context={"offset_minutes": offset},
                    created_by=None,
                )
            )
            existing_offsets.add(offset)
            created += 1
        await self.db.flush()
        return created
