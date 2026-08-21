"""Store copytrade wallet addresses.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-04
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE copytrade_settings "
            "SET enabled = FALSE, strategy_id = NULL "
            "WHERE strategy_id IN ('trader_1', 'trader_2')"
        )
    )
    op.alter_column(
        "copytrade_settings",
        "strategy_id",
        new_column_name="wallet_address",
        existing_type=sa.String(length=64),
    )


def downgrade() -> None:
    op.alter_column(
        "copytrade_settings",
        "wallet_address",
        new_column_name="strategy_id",
        existing_type=sa.String(length=64),
    )
