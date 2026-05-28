"""Хелпер для записи в audit_events.

Используется в эндпоинтах admin: publish/cancel/restore/delete event,
create admin, etc. Не критичен — оборачиваем в try/except,
чтобы не блокировать основное действие.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.models.admin_account import AdminAccount
from app.models.audit_event import AuditEvent

logger = logging.getLogger(__name__)


async def record_audit(
    db,
    *,
    admin: AdminAccount | None,
    action: str,
    target_kind: str | None = None,
    target_id: str | UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        db.add(
            AuditEvent(
                actor_kind="admin" if admin is not None else "system",
                actor_id=str(admin.id) if admin is not None else None,
                action=action,
                target_kind=target_kind,
                target_id=str(target_id) if target_id is not None else None,
                payload=payload,
            )
        )
        await db.flush()
    except Exception:
        logger.exception("record_audit failed: action=%s", action)
