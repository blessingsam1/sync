from solders.keypair import Keypair
from web3 import Web3

from app.database.models import User
from app.security.encryption import SecretEncryption


class UserWalletService:
    def __init__(self, encryption_key: str) -> None:
        self.encryption = SecretEncryption(encryption_key)

    def ensure_wallets(self, user: User) -> bool:
        changed = False
        if not user.sol_wallet_private_key:
            keypair = Keypair()
            user.sol_wallet_address = str(keypair.pubkey())
            user.sol_wallet_private_key = self.encryption.encrypt(str(keypair))
            changed = True
        for chain in ("eth", "bnb"):
            if not getattr(user, f"{chain}_wallet_private_key"):
                account = Web3().eth.account.create()
                setattr(user, f"{chain}_wallet_address", account.address)
                setattr(
                    user, f"{chain}_wallet_private_key",
                    self.encryption.encrypt(account.key.hex()),
                )
                changed = True
        return changed

    def addresses(self, user: User) -> dict[str, str]:
        return {
            "SOL": user.sol_wallet_address or "Unavailable",
            "ETH": user.eth_wallet_address or "Unavailable",
            "BNB": user.bnb_wallet_address or "Unavailable",
        }

    def private_key(self, user: User, chain: str) -> str:
        field = {"solana": "sol", "ethereum": "eth", "bnb": "bnb"}[chain]
        encrypted = getattr(user, f"{field}_wallet_private_key")
        if not encrypted:
            raise ValueError("Wallet has not been generated")
        return self.encryption.decrypt(encrypted)
