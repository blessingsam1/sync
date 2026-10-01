from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class NativeTransferRequest(BaseModel):
    user_id: int | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)
    chain: str
    asset: str
    amount: Decimal = Field(gt=0, decimal_places=18, max_digits=36)
    destination_address: str = Field(min_length=16, max_length=255)

    @field_validator("chain")
    @classmethod
    def validate_chain(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"ethereum", "bnb", "solana"}:
            raise ValueError("Unsupported chain")
        return normalized

    @model_validator(mode="after")
    def validate_chain_asset_pair(self) -> "NativeTransferRequest":
        expected_assets = {"ethereum": "ETH", "bnb": "BNB", "solana": "SOL"}
        self.asset = self.asset.upper()
        if self.asset != expected_assets[self.chain]:
            raise ValueError("Asset does not match the selected mainnet chain")
        return self
