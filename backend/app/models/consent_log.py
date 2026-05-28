import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class ConsentKind(str, enum.Enum):
    TERMS = "terms"
    PHONE = "phone"


class ConsentLog(UUIDPKMixin, Base):
    __tablename__ = "consent_log"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doc_kind: Mapped[ConsentKind] = mapped_column(
        SAEnum(ConsentKind, name="consent_kind"), nullable=False
    )
    doc_version: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("clock_timestamp()"),
        nullable=False,
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
