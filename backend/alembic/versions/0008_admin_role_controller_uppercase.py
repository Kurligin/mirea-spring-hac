"""admin_role: CONTROLLER (uppercase) для соответствия SAEnum по имени

Миграция 0007 добавила в enum admin_role значение 'controller' (lowercase),
но SQLAlchemy SAEnum в этом проекте использует имена-значения (SUPER, EVENT_MANAGER,
VIEWER хранятся в БД именно так). Добавляем 'CONTROLLER' (uppercase),
чтобы insert AdminRole.CONTROLLER работал.

Записей со старым 'controller' пока нет (предыдущие inserts падали).

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-25 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE admin_role ADD VALUE IF NOT EXISTS 'CONTROLLER'")


def downgrade() -> None:
    # Удалить enum-значение в postgres без пересоздания типа нельзя; downgrade пропускаем.
    pass
