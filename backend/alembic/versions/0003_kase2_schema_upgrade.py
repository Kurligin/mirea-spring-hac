"""kase2 schema upgrade: slots, format, short_code, consent, broadcasts

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-15 00:10:46.537889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL ENUM types with create_type=False so create_table won't re-create them
event_format = PgEnum('OFFLINE', 'ONLINE', 'HYBRID', name='event_format', create_type=False)
late_cancellation_policy = PgEnum('FORBID', 'ALLOW_WITH_MARK', name='late_cancellation_policy', create_type=False)
consent_kind = PgEnum('TERMS', 'PHONE', name='consent_kind', create_type=False)
broadcast_kind = PgEnum('TIME_CHANGE', 'VENUE_CHANGE', 'LINK_UPDATE', 'REMINDER_24H', 'REMINDER_1H', name='broadcast_kind', create_type=False)
broadcast_audience = PgEnum('CONFIRMED', 'WAITLIST', 'ALL_ACTIVE', name='broadcast_audience', create_type=False)
broadcast_status = PgEnum('DRAFT', 'SCHEDULED', 'SENDING', 'SENT', 'CANCELLED', name='broadcast_status', create_type=False)
delivery_status = PgEnum('PENDING', 'DELIVERED', 'ERROR', 'MUTED', name='delivery_status', create_type=False)


def upgrade() -> None:
    conn = op.get_bind()

    # Create all new enum types explicitly before they're referenced
    PgEnum('OFFLINE', 'ONLINE', 'HYBRID', name='event_format').create(conn, checkfirst=True)
    PgEnum('FORBID', 'ALLOW_WITH_MARK', name='late_cancellation_policy').create(conn, checkfirst=True)
    PgEnum('TERMS', 'PHONE', name='consent_kind').create(conn, checkfirst=True)
    PgEnum('TIME_CHANGE', 'VENUE_CHANGE', 'LINK_UPDATE', 'REMINDER_24H', 'REMINDER_1H', name='broadcast_kind').create(conn, checkfirst=True)
    PgEnum('CONFIRMED', 'WAITLIST', 'ALL_ACTIVE', name='broadcast_audience').create(conn, checkfirst=True)
    PgEnum('DRAFT', 'SCHEDULED', 'SENDING', 'SENT', 'CANCELLED', name='broadcast_status').create(conn, checkfirst=True)
    PgEnum('PENDING', 'DELIVERED', 'ERROR', 'MUTED', name='delivery_status').create(conn, checkfirst=True)

    # Create new tables (enum types already exist, create_type=False prevents re-creation)
    op.create_table('broadcasts',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('kind', broadcast_kind, nullable=False),
    sa.Column('context', sa.JSON(), nullable=False),
    sa.Column('extra_text', sa.Text(), nullable=True),
    sa.Column('audience', broadcast_audience, nullable=False),
    sa.Column('status', broadcast_status, nullable=False),
    sa.Column('send_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['admin_accounts.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_broadcasts_event_id'), 'broadcasts', ['event_id'], unique=False)
    op.create_index(op.f('ix_broadcasts_status'), 'broadcasts', ['status'], unique=False)

    op.create_table('consent_log',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('doc_kind', consent_kind, nullable=False),
    sa.Column('doc_version', sa.String(length=32), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consent_log_user_id'), 'consent_log', ['user_id'], unique=False)

    op.create_table('event_slots',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=True),
    sa.Column('label', sa.String(length=120), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_event_slots_event_id'), 'event_slots', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_slots_starts_at'), 'event_slots', ['starts_at'], unique=False)

    op.create_table('broadcast_deliveries',
    sa.Column('broadcast_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('status', delivery_status, nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['broadcast_id'], ['broadcasts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('broadcast_id', 'user_id')
    )

    # ALTER TABLE events — add new columns
    op.add_column('events', sa.Column('format', event_format, nullable=False, server_default='OFFLINE'))
    op.add_column('events', sa.Column('online_url', sa.String(length=500), nullable=True))
    op.add_column('events', sa.Column('late_cancellation_policy', late_cancellation_policy, nullable=False, server_default='FORBID'))
    op.add_column('events', sa.Column('slots_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))

    # ALTER TABLE registrations — add new columns
    op.add_column('registrations', sa.Column('slot_id', sa.Uuid(), nullable=True))
    op.add_column('registrations', sa.Column('short_code', sa.String(length=12), nullable=True))
    op.add_column('registrations', sa.Column('notifications_muted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('registrations', sa.Column('is_late_cancellation', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(op.f('ix_registrations_short_code'), 'registrations', ['short_code'], unique=True)
    op.create_index(op.f('ix_registrations_slot_id'), 'registrations', ['slot_id'], unique=False)
    op.create_foreign_key('registrations_slot_id_fkey', 'registrations', 'event_slots', ['slot_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('registrations_slot_id_fkey', 'registrations', type_='foreignkey')
    op.drop_index(op.f('ix_registrations_slot_id'), table_name='registrations')
    op.drop_index(op.f('ix_registrations_short_code'), table_name='registrations')
    op.drop_column('registrations', 'is_late_cancellation')
    op.drop_column('registrations', 'notifications_muted')
    op.drop_column('registrations', 'short_code')
    op.drop_column('registrations', 'slot_id')
    op.drop_column('events', 'slots_enabled')
    op.drop_column('events', 'late_cancellation_policy')
    op.drop_column('events', 'online_url')
    op.drop_column('events', 'format')
    op.drop_table('broadcast_deliveries')
    op.drop_index(op.f('ix_event_slots_starts_at'), table_name='event_slots')
    op.drop_index(op.f('ix_event_slots_event_id'), table_name='event_slots')
    op.drop_table('event_slots')
    op.drop_index(op.f('ix_consent_log_user_id'), table_name='consent_log')
    op.drop_table('consent_log')
    op.drop_index(op.f('ix_broadcasts_status'), table_name='broadcasts')
    op.drop_index(op.f('ix_broadcasts_event_id'), table_name='broadcasts')
    op.drop_table('broadcasts')
    # drop custom enum types (autogenerate omits these)
    conn = op.get_bind()
    PgEnum(name='delivery_status').drop(conn, checkfirst=True)
    PgEnum(name='broadcast_status').drop(conn, checkfirst=True)
    PgEnum(name='broadcast_audience').drop(conn, checkfirst=True)
    PgEnum(name='broadcast_kind').drop(conn, checkfirst=True)
    PgEnum(name='consent_kind').drop(conn, checkfirst=True)
    PgEnum(name='late_cancellation_policy').drop(conn, checkfirst=True)
    PgEnum(name='event_format').drop(conn, checkfirst=True)
