from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.chains import APPROVED_CHAINS
from app.database.models import Balance, ChainCursor, Deposit, User
from app.database.repositories import BalanceRepository
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

_ADDRESS_COLUMN = {
    "ethereum": User.eth_wallet_address,
    "bnb": User.bnb_wallet_address,
    "solana": User.sol_wallet_address,
}
_CASE_INSENSITIVE = {"ethereum", "bnb"}  # EVM addresses differ only by checksum casing


@dataclass(frozen=True)
class IncomingTransfer:
    chain: str  # key from APPROVED_CHAINS: "ethereum" | "bnb" | "solana"
    address: str  # receiving address as seen on-chain
    amount: Decimal  # human units, already converted from wei / lamports
    tx_hash: str
    block_number: int | None = None
    log_index: int = 0


class DepositService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        notifications: NotificationService,
    ) -> None:
        self.session_factory = session_factory
        self.notifications = notifications

    async def watched_addresses(self, chain: str) -> set[str]:
        column = _ADDRESS_COLUMN[chain]
        async with self.session_factory() as s:
            rows = await s.scalars(select(column).where(column.is_not(None)))
            values = {r for r in rows if r}
        return {v.lower() for v in values} if chain in _CASE_INSENSITIVE else values

    async def get_cursor(self, key: str) -> str | None:
        async with self.session_factory() as s:
            row = await s.get(ChainCursor, key)
            return row.value if row else None

    async def set_cursor(self, key: str, value: str) -> None:
        async with self.session_factory() as s:
            row = await s.get(ChainCursor, key)
            if row:
                row.value = value
            else:
                s.add(ChainCursor(key=key, value=value))
            await s.commit()

    async def handle(self, t: IncomingTransfer) -> bool:
        """Record a confirmed transfer and credit the balance, exactly once.

        The Deposit row and the balance credit are committed in ONE transaction,
        so a crash can never credit without a record or record without a credit.
        Returns True only if this call newly credited the transfer.
        """
        definition = APPROVED_CHAINS[t.chain]
        if t.amount <= 0:
            return False
        column = _ADDRESS_COLUMN[t.chain]
        condition = (
            func.lower(column) == t.address.lower()
            if t.chain in _CASE_INSENSITIVE
            else column == t.address
        )

        async with self.session_factory() as s:
            user = await s.scalar(select(User).where(condition))
            if user is None:
                return False
            telegram_id, username = user.telegram_id, user.username

            deposit = Deposit(
                user_id=user.id,
                chain=t.chain,
                asset=definition.asset,
                amount=t.amount,
                tx_hash=t.tx_hash,
                log_index=t.log_index,
                block_number=t.block_number,
            )
            s.add(deposit)
            try:
                await s.flush()
            except IntegrityError:  # already credited: replay after restart/reconnect
                await s.rollback()
                return False

            row = await BalanceRepository(s).get_for_update(user.id, definition.asset)
            if row is None:
                row = Balance(
                    user_id=user.id,
                    chain=t.chain,
                    asset=definition.asset,
                    balance=Decimal("0"),
                    available_balance=Decimal("0"),
                    locked_balance=Decimal("0"),
                )
                s.add(row)
                await s.flush()
            row.balance = Decimal(row.balance) + t.amount
            row.available_balance = Decimal(row.available_balance) + t.amount
            await s.commit()
            deposit_id = deposit.id

        await self._notify(deposit_id, telegram_id, username, t)
        return True

    async def _notify(self, deposit_id: int, telegram_id: int, username: str | None, t: IncomingTransfer) -> None:
        try:
            delivered = await self.notifications.notify_deposit(
                telegram_id=telegram_id,
                username=username,
                chain=APPROVED_CHAINS[t.chain].display_name,
                asset=APPROVED_CHAINS[t.chain].asset,
                amount=t.amount,
                tx_hash=t.tx_hash,
            )
        except Exception:
            logger.exception("Deposit %s credited but notification failed", deposit_id)
            return
        if delivered:
            async with self.session_factory() as s:
                d = await s.get(Deposit, deposit_id)
                if d:
                    d.notified_at = datetime.now(timezone.utc)
                    await s.commit()

    async def resend_unnotified(self) -> int:
        """Run on startup: covers a crash between crediting and notifying."""
        async with self.session_factory() as s:
            rows = (
                await s.execute(
                    select(Deposit, User.telegram_id, User.username)
                    .join(User, User.id == Deposit.user_id)
                    .where(Deposit.notified_at.is_(None))
                )
            ).all()
        for d, telegram_id, username in rows:
            await self._notify(
                d.id, telegram_id, username,
                IncomingTransfer(d.chain, "", Decimal(d.amount), d.tx_hash, d.block_number, d.log_index),
            )
        return len(rows)
