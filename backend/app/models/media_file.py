import enum
from uuid import UUID

from sqlalchemy import ForeignKey, Index, LargeBinary, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class MediaKind(str, enum.Enum):
    EVENT_COVER = "event_cover"
    EVENT_GALLERY = "event_gallery"
    BROADCAST_IMAGE = "broadcast_image"
    BRANDING = "branding"


class MediaFile(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "media_files"
    __table_args__ = (Index("ux_media_sha256", "sha256", unique=True),)

    kind: Mapped[MediaKind] = mapped_column(SAEnum(MediaKind, name="media_kind"), nullable=False)
    event_id: Mapped[UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    uploader_id: Mapped[UUID] = mapped_column(ForeignKey("admin_accounts.id"), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(nullable=False)
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)
    sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
