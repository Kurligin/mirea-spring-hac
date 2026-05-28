"""Сидинг моковых данных для демо.

Создаёт:
- 20 пользователей (User) с уникальными max_user_id 555_001..555_020
- 14 событий в разных статусах (draft / published / cancelled),
  типах (open_day / master_class / olympiad / consultation / other-with-label),
  форматах (offline / online / hybrid), окнах времени (прошедшие / идущие /
  ближайшая неделя / отдалённые) — поверх существующего seed_catalog.py
- Регистрации: ~70 confirmed, ~12 waitlist, ~6 cancelled — равномерно
  по событиям; часть с checked_in_at
- bot_events: для каждой регистрации — event_view → form_start → confirm;
  для ~20% юзеров есть event_view без form_start (drop)

Идемпотентность: проверяет max_user_id / event title / уникальные пары
(user_id, event_id) для регистраций.

Запуск:
    docker compose exec api python -m scripts.seed_demo
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.db import AsyncSessionLocal as async_session_factory
from app.models.bot_event import BotEvent
from app.models.event import (
    Event,
    EventFormat,
    EventStatus,
    EventType,
    LateCancellationPolicy,
)
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.short_code import generate_short_code

MSK = timezone(timedelta(hours=3))
random.seed(42)


def _at(day_offset: int, hour: int) -> datetime:
    now_msk = datetime.now(MSK)
    base = now_msk.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(days=day_offset)


# Дополнительный набор событий для демо (поверх seed_catalog)
DEMO_EVENTS: list[dict] = [
    # Прошедшие — для timeseries-графика
    {"title": "Демо: Открытый день (прошлая неделя)", "event_type": EventType.OPEN_DAY,
     "format": EventFormat.OFFLINE, "starts_at": _at(-9, 11), "location": "Вернадского, 78",
     "capacity": 50, "status": EventStatus.PUBLISHED, "duration_minutes": 180},
    {"title": "Демо: Мастер-класс (3 дня назад)", "event_type": EventType.MASTER_CLASS,
     "format": EventFormat.OFFLINE, "starts_at": _at(-3, 14), "location": "Стромынка, 20",
     "capacity": 25, "status": EventStatus.PUBLISHED, "duration_minutes": 90},
    {"title": "Демо: Олимпиада прошедшая", "event_type": EventType.OLYMPIAD,
     "format": EventFormat.HYBRID, "starts_at": _at(-1, 10), "location": "Вернадского, 78",
     "online_url": "https://meet.example/olymp", "capacity": 80,
     "status": EventStatus.PUBLISHED, "duration_minutes": 180},
    # Идущее сейчас
    {"title": "Демо: ИДЁТ СЕЙЧАС — мастер-класс", "event_type": EventType.MASTER_CLASS,
     "format": EventFormat.OFFLINE, "starts_at": _at(0, datetime.now(MSK).hour),
     "location": "Стромынка, 20", "capacity": 30,
     "status": EventStatus.PUBLISHED, "duration_minutes": 120,
     "late_cancellation_policy": LateCancellationPolicy.ALLOW_WITH_MARK},
    # Ближайшая неделя
    {"title": "Демо: Кастомный тип «Профориентационная игра»",
     "event_type": EventType.OTHER, "custom_type_label": "Профориентационная игра",
     "format": EventFormat.OFFLINE, "starts_at": _at(2, 15), "location": "Вернадского, 78",
     "capacity": 40, "status": EventStatus.PUBLISHED, "duration_minutes": 120},
    {"title": "Демо: Онлайн-консультация по бакалавриату",
     "event_type": EventType.CONSULTATION, "format": EventFormat.ONLINE,
     "starts_at": _at(3, 19), "online_url": "https://meet.example/cons",
     "capacity": 100, "status": EventStatus.PUBLISHED, "duration_minutes": 60},
    {"title": "Демо: Маленькое событие (full)", "event_type": EventType.MASTER_CLASS,
     "format": EventFormat.OFFLINE, "starts_at": _at(4, 13), "location": "Стромынка, 20",
     "capacity": 5, "status": EventStatus.PUBLISHED, "duration_minutes": 60},
    # Дальше
    {"title": "Демо: Олимпиада через 3 недели", "event_type": EventType.OLYMPIAD,
     "format": EventFormat.OFFLINE, "starts_at": _at(21, 10), "location": "Вернадского, 78",
     "capacity": 120, "status": EventStatus.PUBLISHED, "duration_minutes": 180},
    # Черновик и отменённое — для статус-фильтров
    {"title": "Демо: Черновик мастер-класса", "event_type": EventType.MASTER_CLASS,
     "format": EventFormat.OFFLINE, "starts_at": _at(10, 14), "location": "Стромынка, 20",
     "capacity": 30, "status": EventStatus.DRAFT, "duration_minutes": 90},
    {"title": "Демо: Отменённый день открытых дверей", "event_type": EventType.OPEN_DAY,
     "format": EventFormat.OFFLINE, "starts_at": _at(7, 11), "location": "Вернадского, 78",
     "capacity": 60, "status": EventStatus.CANCELLED, "duration_minutes": 180},
]


DEMO_USERS = [
    ("apetrov", "Андрей", "Петров"),
    ("msmirnova", "Мария", "Смирнова"),
    ("ikuznetsov", "Иван", "Кузнецов"),
    ("ekarpova", "Елена", "Карпова"),
    ("sivanov", "Сергей", "Иванов"),
    ("nvolkova", "Наталья", "Волкова"),
    ("dmorozov", "Дмитрий", "Морозов"),
    ("ofedorova", "Ольга", "Фёдорова"),
    ("aborisov", "Алексей", "Борисов"),
    ("vromanov", "Виталий", "Романов"),
    ("ksokolova", "Ксения", "Соколова"),
    ("pleonov", "Павел", "Леонов"),
    ("yzykova", "Юлия", "Зыкова"),
    ("rtikhonov", "Роман", "Тихонов"),
    ("trose", "Тимур", "Розе"),
    ("mlomakin", "Михаил", "Ломакин"),
    ("alarionova", "Алиса", "Ларионова"),
    ("ekulagin", "Егор", "Кулагин"),
    ("vparfenov", "Виктор", "Парфёнов"),
    ("oblinova", "Оксана", "Блинова"),
]


async def ensure_users(db) -> list[User]:
    users: list[User] = []
    for i, (username, first, last) in enumerate(DEMO_USERS, start=1):
        max_id = 555_000 + i
        existing = (
            await db.execute(select(User).where(User.max_user_id == max_id))
        ).scalar_one_or_none()
        if existing is not None:
            users.append(existing)
            continue
        u = User(
            max_user_id=max_id,
            username=username,
            first_name=first,
            last_name=last,
            language_code="ru",
            is_active=True,
        )
        db.add(u)
        users.append(u)
    await db.flush()
    return users


async def ensure_events(db) -> list[Event]:
    existing_titles = set(
        (await db.execute(select(Event.title))).scalars().all()
    )
    events: list[Event] = []
    for spec in DEMO_EVENTS:
        if spec["title"] in existing_titles:
            ev = (
                await db.execute(select(Event).where(Event.title == spec["title"]))
            ).scalar_one()
            events.append(ev)
            continue
        ev = Event(
            title=spec["title"],
            event_type=spec["event_type"],
            custom_type_label=spec.get("custom_type_label"),
            format=spec["format"],
            online_url=spec.get("online_url"),
            location=spec.get("location"),
            starts_at=spec["starts_at"],
            duration_minutes=spec.get("duration_minutes", 60),
            capacity=spec.get("capacity"),
            status=spec.get("status", EventStatus.PUBLISHED),
            waitlist_enabled=True,
            late_cancellation_policy=spec.get(
                "late_cancellation_policy", LateCancellationPolicy.FORBID
            ),
            reminder_offsets_minutes=[1440, 60],
            description=f"Демо-событие: {spec['title']}.",
        )
        db.add(ev)
        events.append(ev)
    await db.flush()
    return events


def _sample_answers(user: User) -> dict:
    return {
        "school": random.choice(["№1234", "Лицей №7", "Гимназия №11", "СОШ №42"]),
        "grade": random.choice(["10", "11", "выпускник"]),
        "interests": random.choice(["ИКБ", "ИИИ", "ИТ", "Кибербезопасность"]),
        "phone": f"+7-9{random.randint(10, 99)}-{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
        "email": f"{(user.username or 'user')}@example.com",
    }


async def ensure_registrations(db, users: list[User], events: list[Event]) -> None:
    """Каждый юзер — на 2-4 события случайно. ~70% confirmed, 15% waitlist, 15% cancelled."""
    pub_events = [e for e in events if e.status == EventStatus.PUBLISHED]
    if not pub_events:
        return
    created = 0
    for user in users:
        picks = random.sample(pub_events, k=min(random.randint(2, 4), len(pub_events)))
        for event in picks:
            existing = (
                await db.execute(
                    select(Registration).where(
                        Registration.user_id == user.id,
                        Registration.event_id == event.id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            roll = random.random()
            if roll < 0.7:
                status = RegistrationStatus.CONFIRMED
            elif roll < 0.85:
                status = RegistrationStatus.WAITLIST
            else:
                status = RegistrationStatus.CANCELLED

            reg = Registration(
                user_id=user.id,
                event_id=event.id,
                status=status,
                answers=_sample_answers(user),
                short_code=generate_short_code(),
                waitlist_position=(
                    random.randint(1, 5)
                    if status == RegistrationStatus.WAITLIST else None
                ),
            )
            # Часть подтверждённых на прошедших событиях — отметим как пришедших
            event_started = event.starts_at < datetime.now(timezone.utc)
            if status == RegistrationStatus.CONFIRMED and event_started and random.random() < 0.55:
                reg.checked_in_at = event.starts_at + timedelta(minutes=random.randint(0, 30))
            if status == RegistrationStatus.CANCELLED:
                reg.cancelled_at = datetime.now(timezone.utc) - timedelta(
                    days=random.randint(0, 5)
                )
                if event_started:
                    reg.is_late_cancellation = True
            db.add(reg)
            created += 1
    await db.flush()
    print(f"  регистраций создано: {created}")


async def ensure_bot_events(db, users: list[User], events: list[Event]) -> None:
    """Воронка: для каждой регистрации создаём event_view → form_start → confirm.
    Плюс ещё дополнительные event_view от ~30% юзеров без последующих шагов (отвал).
    """
    confirmed_pairs = (
        await db.execute(
            select(Registration.user_id, Registration.event_id, Registration.created_at)
            .where(Registration.status == RegistrationStatus.CONFIRMED)
        )
    ).all()
    pub_events = [e for e in events if e.status == EventStatus.PUBLISHED]
    if not pub_events:
        return

    created = 0
    for user_id, event_id, created_at in confirmed_pairs:
        for action, offset_minutes in (
            ("event_view", -15), ("form_start", -10), ("confirm", 0),
        ):
            db.add(BotEvent(
                user_id=user_id,
                event_id=event_id,
                action=action,
                ts=created_at + timedelta(minutes=offset_minutes),
            ))
            created += 1

    # Лишние просмотры — формируют верхний шаг воронки
    for user in users:
        for event in random.sample(pub_events, k=min(2, len(pub_events))):
            if random.random() < 0.3:
                db.add(BotEvent(
                    user_id=user.id,
                    event_id=event.id,
                    action="event_view",
                    ts=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72)),
                ))
                created += 1

    await db.flush()
    print(f"  bot_events создано: {created}")


async def main() -> None:
    async with async_session_factory() as db:
        print("→ Пользователи")
        users = await ensure_users(db)
        print(f"  всего: {len(users)}")

        print("→ События")
        events = await ensure_events(db)
        print(f"  всего: {len(events)}")

        print("→ Регистрации")
        await ensure_registrations(db, users, events)

        print("→ Bot events для воронки")
        await ensure_bot_events(db, users, events)

        await db.commit()
        print("✓ Готово")


if __name__ == "__main__":
    asyncio.run(main())
