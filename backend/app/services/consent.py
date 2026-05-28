from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent_log import ConsentKind, ConsentLog


class ConsentService:
    """Регистрирует согласия и аккумулирует статус по последним версиям.

    Версии документов в коде — при изменении документа поднимаем константу,
    юзеру потребуется заново подтвердить согласие.
    """

    CURRENT_TERMS_VERSION = "v1.0"
    CURRENT_PHONE_VERSION = "v1.0"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        user_id: UUID,
        kind: ConsentKind,
        doc_version: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> ConsentLog:
        log = ConsentLog(
            user_id=user_id,
            doc_kind=kind,
            doc_version=doc_version,
            ip=ip,
            user_agent=user_agent,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def status(self, user_id: UUID) -> dict[ConsentKind, str]:
        """Возвращает {kind: latest_doc_version} только для принятых согласий."""
        stmt = (
            select(ConsentLog.doc_kind, ConsentLog.doc_version, ConsentLog.accepted_at)
            .where(ConsentLog.user_id == user_id)
            .order_by(ConsentLog.accepted_at.desc())
        )
        rows = (await self.db.execute(stmt)).all()
        result: dict[ConsentKind, str] = {}
        for kind, version, _ in rows:
            if kind not in result:
                result[kind] = version
        return result

    async def has_accepted_terms(self, user_id: UUID) -> bool:
        s = await self.status(user_id)
        return s.get(ConsentKind.TERMS) == self.CURRENT_TERMS_VERSION

    async def has_accepted_phone(self, user_id: UUID) -> bool:
        s = await self.status(user_id)
        return s.get(ConsentKind.PHONE) == self.CURRENT_PHONE_VERSION
