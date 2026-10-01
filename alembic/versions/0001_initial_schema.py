"""Initial private testnet trading schema.

Revision ID: 0001
Revises:
Create Date: 2026-08-03
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255)),
        sa.Column("first_name", sa.String(length=255)),
        sa.Column("last_name", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("asset", sa.String(length=16), nullable=False),
        sa.Column(
            "balance",
            sa.Numeric(36, 18),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "available_balance",
            sa.Numeric(36, 18),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "locked_balance",
            sa.Numeric(36, 18),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("balance >= 0", name="ck_balances_balance_nonnegative"),
        sa.CheckConstraint(
            "available_balance >= 0", name="ck_balances_available_nonnegative"
        ),
        sa.CheckConstraint("locked_balance >= 0", name="ck_balances_locked_nonnegative"),
        sa.CheckConstraint(
            "available_balance + locked_balance = balance",
            name="ck_balances_components_equal_total",
        ),
        sa.UniqueConstraint(
            "user_id", "chain", "asset", name="uq_balances_user_chain_asset"
        ),
    )
    op.create_index("ix_balances_user_id", "balances", ["user_id"])

    op.create_table(
        "balance_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("asset", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("previous_balance", sa.Numeric(36, 18), nullable=False),
        sa.Column("new_balance", sa.Numeric(36, 18), nullable=False),
        sa.Column("difference", sa.Numeric(36, 18), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_balance_transactions_user_id", "balance_transactions", ["user_id"]
    )
    op.create_index(
        "ix_balance_transactions_admin_telegram_id",
        "balance_transactions",
        ["admin_telegram_id"],
    )

    op.create_table(
        "copytrade_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("strategy_id", sa.String(length=64)),
        sa.Column(
            "max_trade_amount",
            sa.Numeric(36, 18),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_copytrade_settings_user_id", "copytrade_settings", ["user_id"], unique=True
    )

    op.create_table(
        "autotrade_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "chain", sa.String(length=32), nullable=False, server_default="solana"
        ),
        sa.Column(
            "maximum_trade_amount",
            sa.Numeric(36, 18),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "maximum_daily_trades", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "slippage", sa.Numeric(8, 4), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "strategy", sa.String(length=64), nullable=False, server_default="balanced"
        ),
        sa.Column(
            "take_profit", sa.Numeric(8, 4), nullable=False, server_default=sa.text("10")
        ),
        sa.Column(
            "stop_loss", sa.Numeric(8, 4), nullable=False, server_default=sa.text("5")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_autotrade_settings_user_id", "autotrade_settings", ["user_id"], unique=True
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("asset_in", sa.String(length=32), nullable=False),
        sa.Column("asset_out", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(36, 18), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="simulated"),
        sa.Column("strategy", sa.String(length=64)),
        sa.Column("tx_hash", sa.String(length=255)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_trades_user_id", "trades", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("asset", sa.String(length=16), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(36, 18), nullable=False),
        sa.Column("destination_address", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("tx_hash", sa.String(length=255)),
        sa.Column("error_code", sa.String(length=64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_transactions_idempotency_key"),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index(
        "ix_transactions_idempotency_key",
        "transactions",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "admin_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=64)),
        sa.Column("target_id", sa.String(length=128)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_admin_actions_admin_telegram_id", "admin_actions", ["admin_telegram_id"])

    op.create_table(
        "bot_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_name", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("telegram_id", sa.BigInteger()),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_bot_events_event_type", "bot_events", ["event_type"])
    op.create_index("ix_bot_events_telegram_id", "bot_events", ["telegram_id"])


def downgrade() -> None:
    op.drop_table("bot_events")
    op.drop_table("admin_actions")
    op.drop_table("transactions")
    op.drop_table("trades")
    op.drop_table("autotrade_settings")
    op.drop_table("copytrade_settings")
    op.drop_table("balance_transactions")
    op.drop_table("balances")
    op.drop_table("users")

