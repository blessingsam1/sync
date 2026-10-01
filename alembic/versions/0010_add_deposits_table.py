"""Add deposits table

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'deposits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('chain', sa.String(length=32), nullable=False),
        sa.Column('asset', sa.String(length=16), nullable=False),
        sa.Column('amount', sa.Numeric(precision=30, scale=18), nullable=False),
        sa.Column('tx_hash', sa.String(length=128), nullable=False),
        sa.Column('log_index', sa.Integer(), nullable=False),
        sa.Column('block_number', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('chain', 'tx_hash', 'log_index', name='uq_deposits_transfer'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deposits_user_id', 'deposits', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_deposits_user_id', table_name='deposits')
    op.drop_table('deposits')
