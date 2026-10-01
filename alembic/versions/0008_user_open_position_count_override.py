"""Add user open position count override."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("open_position_count_override", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "open_position_count_override")
