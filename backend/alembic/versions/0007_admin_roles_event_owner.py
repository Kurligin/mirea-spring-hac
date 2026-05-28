"""admin roles + event owner

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-24 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Добавляем CONTROLLER в enum admin_role.
    # ALTER TYPE ... ADD VALUE нельзя внутри транзакции (postgres требует autocommit).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE admin_role ADD VALUE IF NOT EXISTS 'controller'")

    # 2. events.owner_id (nullable сразу, backfill ниже).
    op.add_column(
        "events",
        sa.Column(
            "owner_id",
            sa.UUID(),
            sa.ForeignKey("admin_accounts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )

    # 3. Backfill: первый SUPER admin становится owner-ом всех существующих событий.
    # Значения enum хранятся в верхнем регистре: SUPER, EVENT_MANAGER, VIEWER.
    op.execute(
        """
        UPDATE events SET owner_id = (
            SELECT id FROM admin_accounts
            WHERE role = 'SUPER'
            ORDER BY created_at ASC
            LIMIT 1
        ) WHERE owner_id IS NULL
        """
    )

    # 4. event_controllers (M2M: какие админы-CONTROLLER назначены на какие события).
    op.create_table(
        "event_controllers",
        sa.Column(
            "event_id",
            sa.UUID(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "admin_id",
            sa.UUID(),
            sa.ForeignKey("admin_accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("event_controllers")
    op.drop_column("events", "owner_id")
    # Enum value: для postgres удалить нельзя без пересоздания типа.
    # В рамках хакатона downgrade enum-значения опускаем.
