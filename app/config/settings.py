from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_admin_ids(value: object) -> list[int]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [int(item) for item in value]
    return [int(item.strip()) for item in str(value).split(",") if item.strip()]


AdminIds = Annotated[list[int], BeforeValidator(_parse_admin_ids)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Private Mainnet Trading Bot"
    environment: str = "development"

    user_bot_token: SecretStr = SecretStr("")
    admin_bot_token: SecretStr = SecretStr("")
    database_url: str = "sqlite+aiosqlite:///./testnet_bot.sqlite3"
    admin_telegram_ids: AdminIds = Field(default_factory=list)

    network_mode: Literal["mainnet"] = "mainnet"
    verify_rpc_on_startup: bool = True
    trading_execution_enabled: bool = False
    bot_polling_enabled: bool = True

    eth_wallet_address: str = ""
    eth_private_key: SecretStr = SecretStr("")
    bnb_wallet_address: str = ""
    bnb_private_key: SecretStr = SecretStr("")
    sol_wallet_address: str = ""
    sol_private_key: SecretStr = SecretStr("")

    eth_mainnet_rpc_url: SecretStr = SecretStr("")
    bnb_mainnet_rpc_url: SecretStr = SecretStr("")
    solana_mainnet_rpc_url: SecretStr = SecretStr("")

    encryption_key: SecretStr = SecretStr("")

    @field_validator("network_mode", mode="before")
    @classmethod
    def require_mainnet_mode(cls, value: object) -> str:
        if str(value).lower() != "mainnet":
            raise ValueError("NETWORK_MODE must be exactly 'mainnet'")
        return "mainnet"

    @model_validator(mode="after")
    def validate_mainnet_urls(self) -> "Settings":
        candidates = {
            "ETH_MAINNET_RPC_URL": self.eth_mainnet_rpc_url.get_secret_value(),
            "BNB_MAINNET_RPC_URL": self.bnb_mainnet_rpc_url.get_secret_value(),
            "SOLANA_MAINNET_RPC_URL": self.solana_mainnet_rpc_url.get_secret_value(),
        }
        forbidden_fragments = ("sepolia", "testnet", "devnet")
        for name, url in candidates.items():
            lowered = url.lower()
            if lowered and any(fragment in lowered for fragment in forbidden_fragments):
                raise ValueError(f"{name} appears to reference a non-mainnet endpoint")
        return self

    def wallet_address(self, chain: str) -> str:
        addresses = {
            "ethereum": self.eth_wallet_address,
            "bnb": self.bnb_wallet_address,
            "solana": self.sol_wallet_address,
        }
        try:
            return addresses[chain]
        except KeyError as exc:
            raise ValueError(f"Unsupported chain: {chain}") from exc

    def private_key(self, chain: str) -> SecretStr:
        keys = {
            "ethereum": self.eth_private_key,
            "bnb": self.bnb_private_key,
            "solana": self.sol_private_key,
        }
        try:
            return keys[chain]
        except KeyError as exc:
            raise ValueError(f"Unsupported chain: {chain}") from exc

    def rpc_url(self, chain: str) -> str:
        urls = {
            "ethereum": self.eth_mainnet_rpc_url,
            "bnb": self.bnb_mainnet_rpc_url,
            "solana": self.solana_mainnet_rpc_url,
        }
        try:
            return urls[chain].get_secret_value()
        except KeyError as exc:
            raise ValueError(f"Unsupported chain: {chain}") from exc

    def validate_runtime(self) -> None:
        required = {
            "USER_BOT_TOKEN": self.user_bot_token.get_secret_value(),
            "ADMIN_BOT_TOKEN": self.admin_bot_token.get_secret_value(),
            "ADMIN_TELEGRAM_IDS": self.admin_telegram_ids,
            "ETH_MAINNET_RPC_URL": self.eth_mainnet_rpc_url.get_secret_value(),
            "BNB_MAINNET_RPC_URL": self.bnb_mainnet_rpc_url.get_secret_value(),
            "SOLANA_MAINNET_RPC_URL": self.solana_mainnet_rpc_url.get_secret_value(),
            "ENCRYPTION_KEY": self.encryption_key.get_secret_value(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
