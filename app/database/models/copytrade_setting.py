from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.mixins import TimestampMixin


class CopytradeSetting(TimestampMixin, Base):
    __tablename__ = "copytrade_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wallet_address: Mapped[str | None] = mapped_column(String(64))
    max_trade_amount: Mapped[Decimal] = mapped_column(
        Numeric(36, 18), default=Decimal("0"), nullable=False
    )
