from __future__ import annotations

import json
from decimal import Decimal

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.message import MessageV0
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction

from app.chains.base import BaseChainAdapter, ChainTransferResult
from app.config.settings import Settings
from app.security.network_guard import NetworkGuard


class SolanaMainnetAdapter(BaseChainAdapter):
    chain = "solana"
    asset = "SOL"

    def __init__(self, settings: Settings, network_guard: NetworkGuard) -> None:
        super().__init__(network_guard)
        self.settings = settings

    @staticmethod
    def _load_keypair(secret: str) -> Keypair:
        if secret.lstrip().startswith("["):
            raw = bytes(json.loads(secret))
            return Keypair.from_bytes(raw)
        return Keypair.from_base58_string(secret)

    async def broadcast_native_transfer(
        self, destination_address: str, amount: Decimal
    ) -> ChainTransferResult:
        await self.assert_ready()
        if not self.settings.trading_execution_enabled:
            raise RuntimeError("Transaction broadcasting is disabled")
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        sender = self._load_keypair(self.settings.sol_private_key.get_secret_value())
        if str(sender.pubkey()) != self.settings.sol_wallet_address:
            raise ValueError("Configured private key does not match wallet address")
        destination = Pubkey.from_string(destination_address)
        lamports = int(amount * Decimal("1000000000"))
        if lamports <= 0:
            raise ValueError("Transfer amount is below one lamport")

        client = AsyncClient(self.settings.rpc_url(self.chain))
        try:
            latest = await client.get_latest_blockhash()
            instruction = transfer(
                TransferParams(
                    from_pubkey=sender.pubkey(),
                    to_pubkey=destination,
                    lamports=lamports,
                )
            )
            message = MessageV0.try_compile(
                sender.pubkey(),
                [instruction],
                [],
                latest.value.blockhash,
            )
            transaction = VersionedTransaction(message, [sender])
            response = await client.send_transaction(transaction)
            return ChainTransferResult(tx_hash=str(response.value), chain=self.chain)
        finally:
            await client.close()
