"""increase orders.status length to 32

Revision ID: 0007_orders_status_len_32
Revises: 0006_orders_reject_reason
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007_orders_status_len_32"
down_revision = "0006_orders_reject_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("orders", "status", type_=sa.String(length=32), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("orders", "status", type_=sa.String(length=16), existing_nullable=False)
