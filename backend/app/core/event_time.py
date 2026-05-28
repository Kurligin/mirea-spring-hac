"""Утилиты вокруг времени события: фаза (не начато / идёт / закончилось) и
проверка `is_late` с учётом длительности.

Раньше в коде встречалось `is_late = event.starts_at < now`, что неверно
после конца мероприятия — отмена там бессмысленна, а не «поздняя». Эти
утилиты централизуют логику.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class EventPhase(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


@dataclass(frozen=True)
class EventTiming:
    phase: EventPhase
    starts_at: datetime
    ends_at: datetime


def compute_timing(*, starts_at: datetime, duration_minutes: int, now: datetime) -> EventTiming:
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    if now < starts_at:
        phase = EventPhase.NOT_STARTED
    elif now < ends_at:
        phase = EventPhase.IN_PROGRESS
    else:
        phase = EventPhase.FINISHED
    return EventTiming(phase=phase, starts_at=starts_at, ends_at=ends_at)
