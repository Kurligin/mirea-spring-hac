"""admin_accounts.pin_code_hash — пинкод-логин для проверяющих

Контролёры на входе используют короткий пинкод (4-6 цифр) вместо длинного
пароля — быстрее на мобиле, не требует email-клавиатуры.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-26 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_accounts",
        sa.Column("pin_code_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("admin_accounts", "pin_code_hash")
