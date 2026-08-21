from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from solders.pubkey import Pubkey
from web3 import Web3

from app.database.models import CopytradeSetting


def normalize_wallet_address(value: str) -> str:
    address = value.strip()
    if not address or len(address) > 64:
        raise ValueError("Enter a valid Solana or EVM wallet address")

    if Web3.is_address(address):
        return Web3.to_checksum_address(address)

    try:
        return str(Pubkey.from_string(address))
    except ValueError as exc:
        raise ValueError("Enter a valid Solana or EVM wallet address") from exc


class CopytradeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> CopytradeSetting:
        setting = await self.session.scalar(
            select(CopytradeSetting).where(CopytradeSetting.user_id == user_id)
        )
        if setting is None:
            setting = CopytradeSetting(user_id=user_id)
            self.session.add(setting)
            await self.session.commit()
            await self.session.refresh(setting)
        return setting

    async def follow(self, user_id: int, wallet_address: str) -> CopytradeSetting:
        normalized_address = normalize_wallet_address(wallet_address)
        setting = await self.get(user_id)
        setting.enabled = True
        setting.wallet_address = normalized_address
        await self.session.commit()
        return setting

    async def save_wallet_address(
        self, user_id: int, wallet_address: str
    ) -> CopytradeSetting:
        normalized_address = normalize_wallet_address(wallet_address)
        setting = await self.get(user_id)
        setting.wallet_address = normalized_address
        await self.session.commit()
        return setting

    async def stop(self, user_id: int) -> CopytradeSetting:
        setting = await self.get(user_id)
        setting.enabled = False
        await self.session.commit()
        return setting

    async def start(self, user_id: int) -> CopytradeSetting:
        setting = await self.get(user_id)
        if not setting.wallet_address:
            raise ValueError("Add a wallet address before starting copytrade")
        setting.enabled = True
        await self.session.commit()
        return setting

    async def set_max_trade_amount(
        self, user_id: int, amount: Decimal
    ) -> CopytradeSetting:
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        setting = await self.get(user_id)
        setting.max_trade_amount = amount
        await self.session.commit()
        return setting
