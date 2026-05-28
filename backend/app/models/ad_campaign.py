import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class AdCampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"


class AdCampaign(UUIDPKMixin, TimestampedMixin, Base):
    """Рекламная рассылка всем пользователям бота: заголовок + текст + фото.

    Не привязана к мероприятию (в отличие от Broadcast). send_now → отправка сразу,
    send_at → планировщик (NotificationScheduler) отправит, когда наступит время.
    """

    __tablename__ = "ad_campaigns"

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # путь медиа из /api/admin/uploads (relative к UPLOAD_DIR), опционально
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[AdCampaignStatus] = mapped_column(
        SAEnum(AdCampaignStatus, name="ad_campaign_status"),
        nullable=False,
        default=AdCampaignStatus.DRAFT,
        index=True,
    )
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recipients_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_accounts.id"), nullable=True
    )
