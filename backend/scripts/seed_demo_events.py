"""Витринные мероприятия для демо и тестировщиков.

Создаёт ~10 ОПУБЛИКОВАННЫХ мероприятий только с БУДУЩИМИ датами (от +1 дня),
поэтому они гарантированно видны в каталоге бота (он показывает published + starts_at>=now).
Разные типы (open_day / master_class / olympiad / consultation / other),
форматы (offline / online / hybrid), с описаниями и местами.

Идемпотентность: по title — повторный запуск не плодит дубли.

Запуск (docker, dev):
    docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api python -m scripts.seed_demo_events
Запуск (прод, вариант B):
    docker compose -f docker-compose.deploy.yml exec api python -m scripts.seed_demo_events
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
    """День от сегодня (MSK) в указанный час. day_offset >= 1 → всегда будущее."""
    now_msk = datetime.now(MSK)
    base = now_msk.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(days=max(day_offset, 1))


SEED: list[dict] = [
    {
        "title": "День открытых дверей РТУ МИРЭА",
        "event_type": EventType.OPEN_DAY, "format": EventFormat.OFFLINE,
        "starts_at": _at(3, 12), "duration_minutes": 180,
        "location": "Москва, проспект Вернадского, 78", "capacity": 200,
        "description": "Главное событие для абитуриентов: презентации институтов, "
                       "экскурсии по кампусу, встреча с приёмной комиссией и студентами.",
    },
    {
        "title": "День открытых дверей онлайн",
        "event_type": EventType.OPEN_DAY, "format": EventFormat.ONLINE,
        "starts_at": _at(7, 19), "duration_minutes": 90,
        "online_url": "https://meet.mirea.ru/openday", "capacity": 500,
        "description": "Онлайн-трансляция для тех, кто не может приехать лично. "
                       "Ответим на вопросы в прямом эфире.",
    },
    {
        "title": "Мастер-класс «Python с нуля»",
        "event_type": EventType.MASTER_CLASS, "format": EventFormat.ONLINE,
        "starts_at": _at(2, 18), "duration_minutes": 120,
        "online_url": "https://meet.mirea.ru/python", "capacity": 150,
        "description": "Практическое занятие: пишем первую программу и разбираем, "
                       "как поступить на ИТ-направления.",
        "late_cancellation_policy": LateCancellationPolicy.ALLOW_WITH_MARK,
    },
    {
        "title": "Мастер-класс по робототехнике",
        "event_type": EventType.MASTER_CLASS, "format": EventFormat.OFFLINE,
        "starts_at": _at(5, 16), "duration_minutes": 120,
        "location": "Москва, ул. Стромынка, 20", "capacity": 25,
        "description": "Соберём и запрограммируем робота в лаборатории мехатроники.",
    },
    {
        "title": "Мастер-класс по UI/UX дизайну",
        "event_type": EventType.MASTER_CLASS, "format": EventFormat.OFFLINE,
        "starts_at": _at(9, 17), "duration_minutes": 90,
        "location": "Москва, ул. Стромынка, 20", "capacity": 30,
        "description": "От идеи до прототипа интерфейса: основы дизайна и работа в Figma.",
    },
    {
        "title": "Олимпиада «Кодфест» — отборочный тур",
        "event_type": EventType.OLYMPIAD, "format": EventFormat.HYBRID,
        "starts_at": _at(6, 11), "duration_minutes": 180,
        "location": "Москва, проспект Вернадского, 78",
        "online_url": "https://meet.mirea.ru/codefest", "capacity": 120,
        "description": "Командная олимпиада по программированию. Победители получают "
                       "бонусные баллы к портфолио.",
    },
    {
        "title": "Олимпиада по математике — финал",
        "event_type": EventType.OLYMPIAD, "format": EventFormat.OFFLINE,
        "starts_at": _at(12, 10), "duration_minutes": 240,
        "location": "Москва, проспект Вернадского, 78", "capacity": 80,
        "description": "Заключительный тур для прошедших отбор. Призёрам — льготы при поступлении.",
    },
    {
        "title": "Консультация по программам ИКБ",
        "event_type": EventType.CONSULTATION, "format": EventFormat.ONLINE,
        "starts_at": _at(1, 15), "duration_minutes": 60,
        "online_url": "https://meet.mirea.ru/ikb", "capacity": 200,
        "description": "Институт кибербезопасности: направления, проходные баллы, "
                       "ответы на вопросы поступающих.",
    },
    {
        "title": "Консультация: целевое обучение",
        "event_type": EventType.CONSULTATION, "format": EventFormat.HYBRID,
        "starts_at": _at(4, 16), "duration_minutes": 60,
        "location": "Москва, проспект Вернадского, 78",
        "online_url": "https://meet.mirea.ru/target", "capacity": 60,
        "description": "Как заключить договор о целевом обучении и какие предприятия-партнёры есть.",
    },
    {
        "title": "Экскурсия по кампусу и лабораториям",
        "event_type": EventType.OTHER, "custom_type_label": "Экскурсия",
        "format": EventFormat.OFFLINE,
        "starts_at": _at(8, 14), "duration_minutes": 90,
        "location": "Москва, проспект Вернадского, 78", "capacity": 40,
        "description": "Прогулка по корпусам: лаборатории, коворкинги, библиотека и музей вуза.",
    },
]


async def main() -> None:
    async with async_session_factory() as db:
        existing = set((await db.execute(select(Event.title))).scalars().all())
        created = 0
        for item in SEED:
            if item["title"] in existing:
                continue
            db.add(
                Event(
                    title=item["title"],
                    description=item.get("description"),
                    event_type=item["event_type"],
                    custom_type_label=item.get("custom_type_label"),
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
            )
            created += 1
        await db.commit()
        print(f"seed_demo_events: создано {created}, всего мероприятий теперь {len(existing) + created}")


if __name__ == "__main__":
    asyncio.run(main())
