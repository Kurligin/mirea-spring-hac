"""bot_dialogs.slot_id

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-15 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bot_dialogs", sa.Column("slot_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_bot_dialogs_slot_id", "bot_dialogs", "event_slots",
        ["slot_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_bot_dialogs_slot_id", "bot_dialogs", type_="foreignkey")
    op.drop_column("bot_dialogs", "slot_id")
