"""Store imported private keys encrypted.

Revision ID: 0005
Revises: 0004
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("imported_private_key", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "imported_private_key")
