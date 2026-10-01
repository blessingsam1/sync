"""Allow full token contract addresses in trades.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-07
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite does not support ALTER COLUMN ... TYPE.  Alembic's batch mode
    # recreates the table with the new definition and copies the existing
    # rows, while emitting regular ALTER statements on databases that support
    # them.  This is important for the default SQLite deployment on Railway.
    with op.batch_alter_table("trades") as batch_op:
        batch_op.alter_column(
            "asset_in", existing_type=sa.String(length=32), type_=sa.String(255)
        )
        batch_op.alter_column(
            "asset_out", existing_type=sa.String(length=32), type_=sa.String(255)
        )


def downgrade() -> None:
    with op.batch_alter_table("trades") as batch_op:
        batch_op.alter_column(
            "asset_out", existing_type=sa.String(length=255), type_=sa.String(32)
        )
        batch_op.alter_column(
            "asset_in", existing_type=sa.String(length=255), type_=sa.String(32)
        )
