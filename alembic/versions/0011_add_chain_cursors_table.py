"""Add chain_cursors table

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'chain_cursors',
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('value', sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('chain_cursors')
