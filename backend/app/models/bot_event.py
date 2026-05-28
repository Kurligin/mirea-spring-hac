"""BotEvent — лог действий пользователя в боте для воронки/аналитики.

Действия:
- `event_view` — пользователь открыл карточку события
- `form_start` — начал заполнение анкеты
- `confirm` — нажал «Подтвердить запись» (создалась Registration)

Уникальные пары (user_id, event_id, action) считаются на стороне SQL distinct.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BotEvent(Base):
    __tablename__ = "bot_events"
    __table_args__ = (
        Index("ix_bot_events_action_ts", "action", "ts"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
