"""Store the latest admin position percentage adjustment.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-07
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trades",
        sa.Column(
            "adjustment_percent",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("trades", "adjustment_percent")
