"""add signal linkage to orders

Revision ID: 0002_orders_signal_timeframe
Revises: 0001_initial
Create Date: 2025-01-03 00:10:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_orders_signal_timeframe"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("timeframe", sa.String(length=16), nullable=True))
    op.add_column("orders", sa.Column("signal_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_orders_signal", "orders", "signals", ["signal_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_orders_signal", "orders", type_="foreignkey")
    op.drop_column("orders", "signal_id")
    op.drop_column("orders", "timeframe")
