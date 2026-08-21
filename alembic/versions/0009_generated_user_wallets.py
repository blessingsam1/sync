"""Add generated wallets for each user."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name, length in (
        ("sol_wallet_address", 64), ("sol_wallet_private_key", 1024),
        ("eth_wallet_address", 64), ("eth_wallet_private_key", 1024),
        ("bnb_wallet_address", 64), ("bnb_wallet_private_key", 1024),
    ):
        op.add_column("users", sa.Column(name, sa.String(length=length), nullable=True))


def downgrade() -> None:
    for name in (
        "bnb_wallet_private_key", "bnb_wallet_address",
        "eth_wallet_private_key", "eth_wallet_address",
        "sol_wallet_private_key", "sol_wallet_address",
    ):
        op.drop_column("users", name)
