"""add risk and bracket fields to orders

Revision ID: 0004_orders_risk_fields
Revises: 0003_signal_meta
Create Date: 2026-01-04 03:05:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_orders_risk_fields"
down_revision = "0003_signal_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("stop_loss", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("take_profit", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("take_levels", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("orders", sa.Column("breakeven_at", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("auto_breakeven", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("orders", sa.Column("breakeven_moved", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("orders", sa.Column("stop_order_id", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("take_order_id", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("oco_order_id", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("trade_env", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "trade_env")
    op.drop_column("orders", "oco_order_id")
    op.drop_column("orders", "take_order_id")
    op.drop_column("orders", "stop_order_id")
    op.drop_column("orders", "breakeven_moved")
    op.drop_column("orders", "auto_breakeven")
    op.drop_column("orders", "breakeven_at")
    op.drop_column("orders", "take_levels")
    op.drop_column("orders", "take_profit")
    op.drop_column("orders", "stop_loss")
