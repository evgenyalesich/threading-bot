"""add leverage to orders

Revision ID: 0005_orders_leverage
Revises: 0004_orders_risk_fields
Create Date: 2026-02-07 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_orders_leverage"
down_revision = "0004_orders_risk_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("leverage", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "leverage")

