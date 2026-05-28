"""events.custom_type_label + broadcasts.custom_topic_label

Поле «свой тип» появляется в UI редактора когда выбран event_type=OTHER.
То же для рассылок (broadcast.custom_topic_label).

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-26 19:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("custom_type_label", sa.String(length=80), nullable=True))
    op.add_column("broadcasts", sa.Column("custom_topic_label", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("broadcasts", "custom_topic_label")
    op.drop_column("events", "custom_type_label")
