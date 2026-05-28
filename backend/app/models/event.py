import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedMixin, UUIDPKMixin
from app.models.event_controller import EventController


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class EventType(str, enum.Enum):
    OPEN_DAY = "open_day"
    MASTER_CLASS = "master_class"
    OLYMPIAD = "olympiad"
    CONSULTATION = "consultation"
    OTHER = "other"


class EventFormat(str, enum.Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    HYBRID = "hybrid"


class LateCancellationPolicy(str, enum.Enum):
    FORBID = "forbid"
    ALLOW_WITH_MARK = "allow_with_mark"


class Event(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "events"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType, name="event_type"), nullable=False, default=EventType.OTHER
    )
    # Заполняется только когда event_type == OTHER: «свой» лейбл от организатора
    custom_type_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, name="event_status"),
        nullable=False,
        default=EventStatus.DRAFT,
        index=True,
    )
    format: Mapped[EventFormat] = mapped_column(
        SAEnum(EventFormat, name="event_format"), nullable=False, default=EventFormat.OFFLINE
    )
    online_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    late_cancellation_policy: Mapped[LateCancellationPolicy] = mapped_column(
        SAEnum(LateCancellationPolicy, name="late_cancellation_policy"),
        nullable=False,
        default=LateCancellationPolicy.FORBID,
    )
    slots_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)

    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_lat: Mapped[float | None] = mapped_column(nullable=True)
    location_lng: Mapped[float | None] = mapped_column(nullable=True)

    capacity: Mapped[int | None] = mapped_column(nullable=True)
    waitlist_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    moderation_required: Mapped[bool] = mapped_column(default=False, nullable=False)

    registration_opens_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    registration_closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cover_media_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    reminder_offsets_minutes: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    confirmation_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    max_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    controllers: Mapped[list[EventController]] = relationship(
        "EventController", cascade="all, delete-orphan", lazy="selectin"
    )
    fields: Mapped[list["EventField"]] = relationship(  # noqa: F821
        "EventField",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EventField.order",
    )
