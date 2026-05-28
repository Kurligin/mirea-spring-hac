import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, column
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.event_slot import EventSlot


class RegistrationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    WAITLIST = "waitlist"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


_registration_status_col = SAEnum(RegistrationStatus, name="registration_status")


class Registration(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "registrations"
    __table_args__ = (
        Index(
            "uq_active_registration_per_user_event",
            "user_id",
            "event_id",
            unique=True,
            postgresql_where=column("status", _registration_status_col).in_(
                [
                    RegistrationStatus.CONFIRMED,
                    RegistrationStatus.WAITLIST,
                    RegistrationStatus.PENDING,
                ]
            ),
        ),
        Index("ix_registrations_event_status", "event_id", "status"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[RegistrationStatus] = mapped_column(
        _registration_status_col,
        nullable=False,
        default=RegistrationStatus.CONFIRMED,
    )
    answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    slot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("event_slots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    short_code: Mapped[str | None] = mapped_column(
        String(12), nullable=True, unique=True, index=True
    )
    notifications_muted: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_late_cancellation: Mapped[bool] = mapped_column(default=False, nullable=False)

    waitlist_position: Mapped[int | None] = mapped_column(nullable=True)

    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_accounts.id"), nullable=True
    )
    checked_in_qr_bucket: Mapped[int | None] = mapped_column(nullable=True)

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship("Event", lazy="raise")  # type: ignore
    slot: Mapped["EventSlot"] = relationship("EventSlot", lazy="raise")  # type: ignore
