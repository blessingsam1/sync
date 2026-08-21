from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.mixins import TimestampMixin


class AutotradeSetting(TimestampMixin, Base):
    __tablename__ = "autotrade_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    chain: Mapped[str] = mapped_column(String(32), default="solana", nullable=False)
    maximum_trade_amount: Mapped[Decimal] = mapped_column(
        Numeric(36, 18), default=Decimal("0"), nullable=False
    )
    maximum_daily_trades: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    slippage: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("1"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(String(64), default="balanced", nullable=False)
    take_profit: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("10"), nullable=False
    )
    stop_loss: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("5"), nullable=False
    )

