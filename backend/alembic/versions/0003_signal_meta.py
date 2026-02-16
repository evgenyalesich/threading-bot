"""add meta field to signals

Revision ID: 0003_signal_meta
Revises: 0002_orders_signal_timeframe
Create Date: 2026-01-04 02:10:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_signal_meta"
down_revision = "0002_orders_signal_timeframe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "meta")
