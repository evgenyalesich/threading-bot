"""add order exit fields

Revision ID: 0008_orders_exit_fields
Revises: 0007_orders_status_len_32
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_orders_exit_fields"
down_revision = "0007_orders_status_len_32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("exit_price", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("realized_pnl", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "closed_at")
    op.drop_column("orders", "realized_pnl")
    op.drop_column("orders", "exit_price")
