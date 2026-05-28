"""ad_campaigns — рекламные рассылки всем пользователям бота

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-28 21:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "ad_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column(
            # SAEnum(AdCampaignStatus) хранит ИМЕНА членов (uppercase), а не values —
            # как admin_role/broadcast_status в этом проекте. Поэтому значения тут — имена.
            "status",
            sa.Enum("DRAFT", "SCHEDULED", "SENDING", "SENT", name="ad_campaign_status"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipients_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("admin_accounts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ad_campaigns_status", "ad_campaigns", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ad_campaigns_status", table_name="ad_campaigns")
    op.drop_table("ad_campaigns")
    sa.Enum(name="ad_campaign_status").drop(op.get_bind(), checkfirst=True)
