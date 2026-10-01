from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.chains import ASSET_TO_CHAIN
from app.database.models import AdminAction, Balance, BalanceTransaction
from app.database.repositories import BalanceRepository
from app.schemas.balance import BalanceAdjustment, BalanceAdjustmentAction


class BalanceConflictError(RuntimeError):
    pass


class InsufficientBalanceError(ValueError):
    pass


class BalanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.balances = BalanceRepository(session)

    async def list_for_user(self, user_id: int) -> dict[str, Decimal]:
        rows = await self.balances.list_for_user(user_id)
        result = {"SOL": Decimal("0"), "ETH": Decimal("0"), "BNB": Decimal("0")}
        result.update({row.asset: row.balance for row in rows})
        return result

    async def adjust(self, adjustment: BalanceAdjustment) -> BalanceTransaction:
        asset = adjustment.asset
        row = await self.balances.get_for_update(adjustment.user_id, asset)
        if row is None:
            row = Balance(
                user_id=adjustment.user_id,
                chain=ASSET_TO_CHAIN[asset],
                asset=asset,
                balance=Decimal("0"),
                available_balance=Decimal("0"),
                locked_balance=Decimal("0"),
            )
            self.session.add(row)
            await self.session.flush()

        previous = Decimal(row.balance)
        if (
            adjustment.expected_previous_balance is not None
            and previous != adjustment.expected_previous_balance
        ):
            raise BalanceConflictError("Balance changed before confirmation")

        if adjustment.action == BalanceAdjustmentAction.ADD:
            new_balance = previous + adjustment.amount
        elif adjustment.action == BalanceAdjustmentAction.SUBTRACT:
            if adjustment.amount > row.available_balance:
                raise InsufficientBalanceError("Amount exceeds available balance")
            new_balance = previous - adjustment.amount
        else:
            new_balance = adjustment.amount
            if new_balance < row.locked_balance:
                raise InsufficientBalanceError("New balance cannot be below locked balance")

        difference = new_balance - previous
        row.balance = new_balance
        row.available_balance = new_balance - row.locked_balance

        audit = BalanceTransaction(
            user_id=adjustment.user_id,
            admin_telegram_id=adjustment.admin_telegram_id,
            chain=row.chain,
            asset=asset,
            action=adjustment.action.value,
            previous_balance=previous,
            new_balance=new_balance,
            difference=difference,
            reason=adjustment.reason,
        )
        self.session.add(audit)
        self.session.add(
            AdminAction(
                admin_telegram_id=adjustment.admin_telegram_id,
                action="balance_adjustment",
                target_type="user",
                target_id=str(adjustment.user_id),
                details={
                    "asset": asset,
                    "operation": adjustment.action.value,
                    "previous": str(previous),
                    "new": str(new_balance),
                    "difference": str(difference),
                    "reason": adjustment.reason,
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(audit)
        return audit

