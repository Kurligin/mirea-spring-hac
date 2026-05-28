import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class BroadcastKind(str, enum.Enum):
    TIME_CHANGE = "time_change"
    VENUE_CHANGE = "venue_change"
    LINK_UPDATE = "link_update"
    REMINDER_24H = "reminder_24h"
    REMINDER_1H = "reminder_1h"
    OTHER = "other"


class BroadcastAudience(str, enum.Enum):
    CONFIRMED = "confirmed"
    WAITLIST = "waitlist"
    ALL_ACTIVE = "all_active"


class BroadcastStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    ERROR = "error"
    MUTED = "muted"


class Broadcast(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "broadcasts"

    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[BroadcastKind] = mapped_column(SAEnum(BroadcastKind, name="broadcast_kind"), nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    extra_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience: Mapped[BroadcastAudience] = mapped_column(
        SAEnum(BroadcastAudience, name="broadcast_audience"), nullable=False, default=BroadcastAudience.CONFIRMED
    )
    status: Mapped[BroadcastStatus] = mapped_column(
        SAEnum(BroadcastStatus, name="broadcast_status"), nullable=False, default=BroadcastStatus.DRAFT, index=True
    )
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("admin_accounts.id"), nullable=True)
    custom_topic_label: Mapped[str | None] = mapped_column(String(80), nullable=True)


class BroadcastDelivery(Base):
    __tablename__ = "broadcast_deliveries"

    broadcast_id: Mapped[UUID] = mapped_column(ForeignKey("broadcasts.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"), nullable=False, default=DeliveryStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
