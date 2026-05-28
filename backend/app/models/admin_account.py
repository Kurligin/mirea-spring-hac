import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class AdminRole(str, enum.Enum):
    SUPER = "super"
    EVENT_MANAGER = "event_manager"
    VIEWER = "viewer"
    CONTROLLER = "controller"


class AdminAccount(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "admin_accounts"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        SAEnum(AdminRole, name="admin_role"), nullable=False, default=AdminRole.EVENT_MANAGER
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    pin_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
