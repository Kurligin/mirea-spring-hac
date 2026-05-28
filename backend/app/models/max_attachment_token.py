from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin


class MaxAttachmentToken(TimestampedMixin, Base):
    __tablename__ = "max_attachment_tokens"

    media_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_files.id", ondelete="CASCADE"), primary_key=True
    )
    max_token: Mapped[str] = mapped_column(String(500), nullable=False)
    max_url: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
