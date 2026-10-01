from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.balance import BALANCE_PRECISION, BALANCE_SCALE


class Deposit(Base):
    """One confirmed on-chain transfer into a user's deposit address.

    This table is the source of truth behind every credited balance. The unique
    constraint guarantees a transfer can be credited at most once, even if a
    watcher restarts, replays blocks, or two processes run by mistake.
    """

    __tablename__ = "deposits"
    __table_args__ = (
        UniqueConstraint("chain", "tx_hash", "log_index", name="uq_deposits_transfer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(BALANCE_PRECISION, BALANCE_SCALE), nullable=False
    )
    tx_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    log_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    block_number: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChainCursor(Base):
    """Where each watcher left off, so restarts neither skip nor replay history."""

    __tablename__ = "chain_cursors"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
