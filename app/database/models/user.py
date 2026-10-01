from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    imported_private_key: Mapped[str | None] = mapped_column(String(1024))
    open_position_count_override: Mapped[int | None] = mapped_column(Integer)
    sol_wallet_address: Mapped[str | None] = mapped_column(String(64))
    sol_wallet_private_key: Mapped[str | None] = mapped_column(String(1024))
    eth_wallet_address: Mapped[str | None] = mapped_column(String(64))
    eth_wallet_private_key: Mapped[str | None] = mapped_column(String(1024))
    bnb_wallet_address: Mapped[str | None] = mapped_column(String(64))
    bnb_wallet_private_key: Mapped[str | None] = mapped_column(String(1024))

    balances: Mapped[list["Balance"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
