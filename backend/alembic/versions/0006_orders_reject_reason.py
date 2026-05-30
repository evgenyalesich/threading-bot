"""add reject reason to orders

Revision ID: 0006_orders_reject_reason
Revises: 0005_orders_leverage
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_orders_reject_reason"
down_revision = "0005_orders_leverage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("reject_reason", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "reject_reason")
