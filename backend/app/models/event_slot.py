from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class EventSlot(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "event_slots"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    capacity: Mapped[int | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
