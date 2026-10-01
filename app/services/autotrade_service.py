from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AutotradeSetting


class AutotradeService:
    EDITABLE_DECIMAL_FIELDS = {
        "maximum_trade_amount",
        "slippage",
        "take_profit",
        "stop_loss",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> AutotradeSetting:
        setting = await self.session.scalar(
            select(AutotradeSetting).where(AutotradeSetting.user_id == user_id)
        )
        if setting is None:
            setting = AutotradeSetting(user_id=user_id)
            self.session.add(setting)
            await self.session.commit()
            await self.session.refresh(setting)
        return setting

    async def toggle(self, user_id: int) -> AutotradeSetting:
        setting = await self.get(user_id)
        setting.enabled = not setting.enabled
        await self.session.commit()
        return setting

    async def set_chain(self, user_id: int, chain: str) -> AutotradeSetting:
        if chain not in {"solana", "ethereum", "bnb"}:
            raise ValueError("Unsupported chain")
        setting = await self.get(user_id)
        setting.chain = chain
        await self.session.commit()
        return setting

    async def set_strategy(self, user_id: int, strategy: str) -> AutotradeSetting:
        if strategy not in {"conservative", "balanced", "aggressive"}:
            raise ValueError("Unsupported strategy")
        setting = await self.get(user_id)
        setting.strategy = strategy
        await self.session.commit()
        return setting

    async def set_numeric(self, user_id: int, field: str, value: Decimal) -> AutotradeSetting:
        if field == "maximum_daily_trades":
            integer_value = int(value)
            if value != integer_value or not 1 <= integer_value <= 100:
                raise ValueError("Daily trades must be a whole number from 1 to 100")
            setting = await self.get(user_id)
            setting.maximum_daily_trades = integer_value
        elif field in self.EDITABLE_DECIMAL_FIELDS:
            if value < 0:
                raise ValueError("Value cannot be negative")
            if field in {"slippage", "take_profit", "stop_loss"} and value > 100:
                raise ValueError("Percentage cannot exceed 100")
            setting = await self.get(user_id)
            setattr(setting, field, value)
        else:
            raise ValueError("Unsupported setting")
        await self.session.commit()
        return setting

