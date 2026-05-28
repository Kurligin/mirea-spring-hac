import enum
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class DialogState(str, enum.Enum):
    IDLE = "idle"
    ASKING_FIELD = "asking_field"
    CONFIRMING = "confirming"
    DONE = "done"


class BotDialog(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "bot_dialogs"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_dialog_user_event"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[DialogState] = mapped_column(
        SAEnum(DialogState, name="dialog_state"), nullable=False, default=DialogState.IDLE
    )
    current_field_index: Mapped[int] = mapped_column(default=0, nullable=False)
    answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    slot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("event_slots.id", ondelete="SET NULL"), nullable=True
    )
    skip_phone: Mapped[bool] = mapped_column(default=False, nullable=False)
