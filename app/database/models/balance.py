from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime
from datetime import datetime

from app.database.base import Base

BALANCE_PRECISION = 36
BALANCE_SCALE = 18


class Balance(Base):
    __tablename__ = "balances"
    __table_args__ = (
        UniqueConstraint("user_id", "chain", "asset", name="uq_balances_user_chain_asset"),
        CheckConstraint("balance >= 0", name="ck_balances_balance_nonnegative"),
        CheckConstraint("available_balance >= 0", name="ck_balances_available_nonnegative"),
        CheckConstraint("locked_balance >= 0", name="ck_balances_locked_nonnegative"),
        CheckConstraint(
            "available_balance + locked_balance = balance",
            name="ck_balances_components_equal_total",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(BALANCE_PRECISION, BALANCE_SCALE), default=Decimal("0"), nullable=False
    )
    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(BALANCE_PRECISION, BALANCE_SCALE), default=Decimal("0"), nullable=False
    )
    locked_balance: Mapped[Decimal] = mapped_column(
        Numeric(BALANCE_PRECISION, BALANCE_SCALE), default=Decimal("0"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="balances")

