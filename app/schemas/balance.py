from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class BalanceAdjustmentAction(StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    SET = "set"


class BalanceAdjustment(BaseModel):
    user_id: int
    admin_telegram_id: int
    asset: str
    action: BalanceAdjustmentAction
    amount: Decimal = Field(decimal_places=18, max_digits=36)
    reason: str = Field(min_length=3, max_length=500)
    expected_previous_balance: Decimal | None = None

    @field_validator("asset")
    @classmethod
    def validate_asset(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"SOL", "ETH", "BNB"}:
            raise ValueError("Unsupported asset")
        return normalized

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal, info) -> Decimal:
        action = info.data.get("action")
        if action in {BalanceAdjustmentAction.ADD, BalanceAdjustmentAction.SUBTRACT}:
            if value <= 0:
                raise ValueError("Add and subtract amounts must be greater than zero")
        elif value < 0:
            raise ValueError("Balance cannot be negative")
        return value

