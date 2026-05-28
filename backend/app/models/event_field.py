import enum
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class FieldType(str, enum.Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CONSENT = "consent"


class EventField(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "event_fields"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[int] = mapped_column(nullable=False, default=0)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    placeholder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    field_type: Mapped[FieldType] = mapped_column(
        SAEnum(FieldType, name="field_type"), nullable=False
    )
    required: Mapped[bool] = mapped_column(default=False, nullable=False)
    options: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="fields")
