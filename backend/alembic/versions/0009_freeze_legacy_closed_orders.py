"""freeze legacy closed order pnl

Revision ID: 0009_freeze_legacy_closed_orders
Revises: 0008_orders_exit_fields
Create Date: 2026-05-29
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0009_freeze_legacy_closed_orders"
down_revision = "0008_orders_exit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older closed orders predate exit snapshots. Preserve them as fixed zero-PnL
    # records instead of letting clients accidentally attach live market data.
    op.execute(
        """
        UPDATE orders
        SET exit_price = COALESCE(exit_price, price),
            realized_pnl = COALESCE(realized_pnl, 0),
            closed_at = COALESCE(closed_at, created_at)
        WHERE status IN ('closed', 'filled', 'cancelled')
          AND (exit_price IS NULL OR realized_pnl IS NULL OR closed_at IS NULL)
        """
    )


def downgrade() -> None:
    # Historical values cannot be distinguished from genuine zero-PnL exits.
    pass
