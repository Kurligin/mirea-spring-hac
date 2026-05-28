"""Централизованные проверки прав доступа для админ-API.

Все эндпоинты, работающие с конкретным Event, ДОЛЖНЫ вызывать
`assert_can_access_event(admin, event)`. Это инкапсулирует бизнес-правила:

- SUPER — видит/правит всё.
- EVENT_MANAGER — только свои события (Event.owner_id == admin.id).
- CONTROLLER — только события, где он в `event_controllers`.
- VIEWER — ничего из event-scoped (только глобальная статистика).

Использует `event.controllers` (selectinload или joined) — вызывающий
код должен обеспечить загрузку.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.models.admin_account import AdminRole


def can_access_event(admin: object, event: object) -> bool:
    role = admin.role  # type: ignore[attr-defined]
    if role == AdminRole.SUPER:
        return True
    if role == AdminRole.EVENT_MANAGER:
        return event.owner_id == admin.id  # type: ignore[attr-defined]
    if role == AdminRole.CONTROLLER:
        return any(
            c.admin_id == admin.id  # type: ignore[attr-defined]
            for c in event.controllers  # type: ignore[attr-defined]
        )
    return False  # VIEWER и unknown — без доступа к event-scoped операциям.


def assert_can_access_event(admin: object, event: object) -> None:
    if not can_access_event(admin, event):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
