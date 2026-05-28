from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.admin_account import AdminRole
from app.models.base import Base, TimestampedMixin, UUIDPKMixin


class User(UUIDPKMixin, TimestampedMixin, Base):
    __tablename__ = "users"

    max_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    admin_role: Mapped[AdminRole | None] = mapped_column(
        SAEnum(AdminRole, name="admin_role", create_type=False), nullable=True
    )
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
