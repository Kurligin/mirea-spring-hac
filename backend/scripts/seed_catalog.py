"""Сидинг каталога для ручных smoke-тестов (запуск внутри docker compose exec api).

Назначение: создаёт ~12 событий с разнообразными комбинациями
event_type × format × дата, чтобы покрыть пикеры/пагинацию/поиск.

Идемпотентность: проверяет существующий title; добавляет только недостающие.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import AsyncSessionLocal as async_session_factory
from app.models.event import (
    Event,
    EventFormat,
    EventStatus,
    EventType,
    LateCancellationPolicy,
)

MSK = timezone(timedelta(hours=3))


def _at(day_offset: int, hour: int) -> datetime:
    """День от сегодня (MSK) в указанный час."""
    now_msk = datetime.now(MSK)
    base = now_msk.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(days=day_offset)


SEED: list[dict] = [
    # Сегодня
    {"title": "Открытый день — основной кампус", "event_type": EventType.OPEN_DAY,
     "format": EventFormat.OFFLINE, "starts_at": _at(0, 11), "location": "Вернадского, 78",
     "capacity": 40},
    {"title": "Консультация по программам ИКБ", "event_type": EventType.CONSULTATION,
     "format": EventFormat.ONLINE, "starts_at": _at(0, 15), "online_url": "https://meet.example/ikb",
     "capacity": 200},
    {"title": "Мастер-класс по робототехнике",  "event_type": EventType.MASTER_CLASS,
     "format": EventFormat.OFFLINE, "starts_at": _at(0, 17), "location": "Стромынка, 20",
     "capacity": 25, "late_cancellation_policy": LateCancellationPolicy.ALLOW_WITH_MARK},
    # На неделе (1-6 дней)
    {"title": "Олимпиада «Кодфест» — отбор",   "event_type": EventType.OLYMPIAD,
     "format": EventFormat.HYBRID,  "starts_at": _at(2, 12), "capacity": 100,
     "location": "Вернадского, 78", "online_url": "https://meet.example/codefest"},
    {"title": "Мастер-класс: Python для абитуриентов", "event_type": EventType.MASTER_CLASS,
     "format": EventFormat.ONLINE, "starts_at": _at(3, 18), "online_url": "https://meet.example/py",
     "capacity": 150},
    {"title": "День открытых дверей ИИИ",      "event_type": EventType.OPEN_DAY,
     "format": EventFormat.OFFLINE, "starts_at": _at(4, 13), "location": "Стромынка, 20",
     "capacity": 60},
    {"title": "Консультация: целевой набор",   "event_type": EventType.CONSULTATION,
     "format": EventFormat.HYBRID, "starts_at": _at(5, 16), "location": "Вернадского, 78",
     "online_url": "https://meet.example/target", "capacity": 50},
    {"title": "Прочее: экскурсия по библиотеке","event_type": EventType.OTHER,
     "format": EventFormat.OFFLINE, "starts_at": _at(6, 14), "location": "Вернадского, 78",
     "capacity": 30},
    # Дальше недели
    {"title": "Мастер-класс по дизайну UI/UX", "event_type": EventType.MASTER_CLASS,
     "format": EventFormat.OFFLINE, "starts_at": _at(10, 17), "location": "Стромынка, 20",
     "capacity": 20},
    {"title": "Олимпиада по математике — финал","event_type": EventType.OLYMPIAD,
     "format": EventFormat.OFFLINE, "starts_at": _at(12, 10), "location": "Вернадского, 78",
     "capacity": 80},
    {"title": "День открытых дверей онлайн",   "event_type": EventType.OPEN_DAY,
     "format": EventFormat.ONLINE,  "starts_at": _at(14, 19), "online_url": "https://meet.example/od",
     "capacity": 300},
    {"title": "Консультация для родителей",    "event_type": EventType.CONSULTATION,
     "format": EventFormat.ONLINE,  "starts_at": _at(15, 19), "online_url": "https://meet.example/parents",
     "capacity": 200},
]


async def main() -> None:
    async with async_session_factory() as db:
        existing_titles = set(
            (await db.execute(select(Event.title))).scalars().all()
        )
        created = 0
        for item in SEED:
            if item["title"] in existing_titles:
                continue
            ev = Event(
                title=item["title"],
                description=None,
                event_type=item["event_type"],
                status=EventStatus.PUBLISHED,
                format=item["format"],
                online_url=item.get("online_url"),
                late_cancellation_policy=item.get(
                    "late_cancellation_policy", LateCancellationPolicy.FORBID
                ),
                slots_enabled=False,
                starts_at=item["starts_at"],
                duration_minutes=item.get("duration_minutes", 60),
                location=item.get("location"),
                capacity=item.get("capacity"),
                waitlist_enabled=True,
                moderation_required=False,
                reminder_offsets_minutes=[60, 1440],
            )
            db.add(ev)
            created += 1
        await db.commit()
        print(f"seed: создано {created}, всего теперь {len(existing_titles) + created}")


if __name__ == "__main__":
    asyncio.run(main())
