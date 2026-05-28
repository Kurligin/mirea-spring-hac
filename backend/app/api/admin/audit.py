"""GET /api/admin/audit — лог действий, только для SUPER.

Фильтры: action, actor_id, target_kind, target_id. Сортировка — created_at DESC.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.models.admin_account import AdminAccount, AdminRole
from app.models.audit_event import AuditEvent

router = APIRouter(prefix="/api/admin/audit", tags=["admin-audit"])


class AuditEntry(BaseModel):
    id: UUID
    actor_kind: str
    actor_id: str | None
    actor_email: str | None = None
    action: str
    target_kind: str | None
    target_id: str | None
    payload: dict[str, Any] | None
    created_at: datetime


@router.get("", response_model=list[AuditEntry])
async def list_audit(
    action: str | None = Query(None),
    actor_id: str | None = Query(None),
    target_kind: str | None = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    if admin.role != AdminRole.SUPER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super-admin can view audit log")

    stmt = (
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if target_kind:
        stmt = stmt.where(AuditEvent.target_kind == target_kind)

    rows = list((await db.execute(stmt)).scalars().all())

    # Подтягиваем email админов одним запросом
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    emails: dict[str, str] = {}
    if actor_ids:
        try:
            admin_rows = (
                await db.execute(
                    select(AdminAccount.id, AdminAccount.email).where(
                        AdminAccount.id.in_([UUID(x) for x in actor_ids])
                    )
                )
            ).all()
            emails = {str(aid): email for aid, email in admin_rows}
        except (ValueError, Exception):
            pass

    return [
        AuditEntry(
            id=r.id,
            actor_kind=r.actor_kind,
            actor_id=r.actor_id,
            actor_email=emails.get(r.actor_id or ""),
            action=r.action,
            target_kind=r.target_kind,
            target_id=r.target_id,
            payload=r.payload,
            created_at=r.created_at,
        )
        for r in rows
    ]
