from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def list_paginated(self, page: int, page_size: int) -> tuple[list[User], int]:
        total = await self.session.scalar(select(func.count()).select_from(User)) or 0
        result = await self.session.scalars(
            select(User)
            .order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result), total

    def add(self, user: User) -> None:
        self.session.add(user)

