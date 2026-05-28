"""broadcast_kind: добавить значение OTHER (uppercase для SAEnum по имени)

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-26 19:30:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE broadcast_kind ADD VALUE IF NOT EXISTS 'OTHER'")


def downgrade() -> None:
    # Удалить значение enum в postgres без пересоздания типа нельзя.
    pass
