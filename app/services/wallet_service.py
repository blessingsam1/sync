from __future__ import annotations

import json

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from web3 import Web3

from app.config.settings import Settings


class WalletConfigurationError(ValueError):
    pass


class WalletService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def public_addresses(self) -> dict[str, str]:
        return {
            "SOL": self.settings.sol_wallet_address,
            "ETH": self.settings.eth_wallet_address,
            "BNB": self.settings.bnb_wallet_address,
        }

    def private_key_for_admin(self, chain: str) -> str:
        return self.settings.private_key(chain).get_secret_value()

    def validate_configuration(self) -> None:
        if not Web3.is_address(self.settings.eth_wallet_address):
            raise WalletConfigurationError("ETH_WALLET_ADDRESS is invalid")
        if not Web3.is_address(self.settings.bnb_wallet_address):
            raise WalletConfigurationError("BNB_WALLET_ADDRESS is invalid")
        try:
            sol_address = Pubkey.from_string(self.settings.sol_wallet_address)
        except ValueError as exc:
            raise WalletConfigurationError("SOL_WALLET_ADDRESS is invalid") from exc

        if not self.settings.trading_execution_enabled:
            return

        account_api = Web3().eth.account
        try:
            eth_account = account_api.from_key(
                self.settings.eth_private_key.get_secret_value()
            )
            bnb_account = account_api.from_key(
                self.settings.bnb_private_key.get_secret_value()
            )
        except Exception as exc:
            raise WalletConfigurationError("An EVM private key is invalid") from exc
        if eth_account.address.lower() != self.settings.eth_wallet_address.lower():
            raise WalletConfigurationError("ETH private key does not match its address")
        if bnb_account.address.lower() != self.settings.bnb_wallet_address.lower():
            raise WalletConfigurationError("BNB private key does not match its address")

        try:
            sol_secret = self.settings.sol_private_key.get_secret_value()
            if sol_secret.lstrip().startswith("["):
                sol_keypair = Keypair.from_bytes(bytes(json.loads(sol_secret)))
            else:
                sol_keypair = Keypair.from_base58_string(sol_secret)
        except Exception as exc:
            raise WalletConfigurationError("SOL private key is invalid") from exc
        if sol_keypair.pubkey() != sol_address:
            raise WalletConfigurationError("SOL private key does not match its address")
