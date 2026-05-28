"""bot_dialogs.skip_phone

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-18 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bot_dialogs",
        sa.Column("skip_phone", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("bot_dialogs", "skip_phone", server_default=None)


def downgrade() -> None:
    op.drop_column("bot_dialogs", "skip_phone")
