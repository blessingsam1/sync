from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Balance


class BalanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: int) -> list[Balance]:
        result = await self.session.scalars(
            select(Balance).where(Balance.user_id == user_id).order_by(Balance.asset)
        )
        return list(result)

    async def get_for_update(self, user_id: int, asset: str) -> Balance | None:
        return await self.session.scalar(
            select(Balance)
            .where(Balance.user_id == user_id, Balance.asset == asset)
            .with_for_update()
        )

