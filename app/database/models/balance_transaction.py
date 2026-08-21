from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.balance import BALANCE_PRECISION, BALANCE_SCALE


class BalanceTransaction(Base):
    __tablename__ = "balance_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    previous_balance: Mapped[Decimal] = mapped_column(
        Numeric(BALANCE_PRECISION, BALANCE_SCALE), nullable=False
    )
    new_balance: Mapped[Decimal] = mapped_column(
        Numeric(BALANCE_PRECISION, BALANCE_SCALE), nullable=False
    )
    difference: Mapped[Decimal] = mapped_column(
        Numeric(BALANCE_PRECISION, BALANCE_SCALE), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

