from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.chains import APPROVED_CHAINS
from app.database.models import AutotradeSetting, Balance, CopytradeSetting, User
from app.database.repositories import UserRepository


@dataclass(frozen=True)
class TelegramUserData:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def get_or_create(self, data: TelegramUserData) -> tuple[User, bool]:
        existing = await self.users.get_by_telegram_id(data.telegram_id)
        if existing is not None:
            existing.username = data.username
            existing.first_name = data.first_name
            existing.last_name = data.last_name
            await self.session.commit()
            return existing, False

        user = User(
            telegram_id=data.telegram_id,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=True,
        )
        self.users.add(user)
        try:
            await self.session.flush()
            for chain, definition in APPROVED_CHAINS.items():
                self.session.add(
                    Balance(
                        user_id=user.id,
                        chain=chain,
                        asset=definition.asset,
                        balance=Decimal("0"),
                        available_balance=Decimal("0"),
                        locked_balance=Decimal("0"),
                    )
                )
            self.session.add(CopytradeSetting(user_id=user.id))
            self.session.add(AutotradeSetting(user_id=user.id))
            await self.session.commit()
            await self.session.refresh(user)
            return user, True
        except IntegrityError:
            await self.session.rollback()
            raced_user = await self.users.get_by_telegram_id(data.telegram_id)
            if raced_user is None:
                raise
            return raced_user, False

    async def set_active(self, user_id: int, active: bool) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise LookupError("User not found")
        user.is_active = active
        await self.session.commit()
        await self.session.refresh(user)
        return user

