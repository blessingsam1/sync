from __future__ import annotations

from decimal import Decimal

from web3 import AsyncHTTPProvider, AsyncWeb3

from app.chains.base import BaseChainAdapter, ChainTransferResult
from app.config.settings import Settings
from app.security.network_guard import NetworkGuard, NetworkGuardError


class EVMChainAdapter(BaseChainAdapter):
    expected_chain_id: int

    def __init__(self, settings: Settings, network_guard: NetworkGuard) -> None:
        super().__init__(network_guard)
        self.settings = settings

    async def broadcast_native_transfer(
        self, destination_address: str, amount: Decimal
    ) -> ChainTransferResult:
        await self.assert_ready()
        if not self.settings.trading_execution_enabled:
            raise RuntimeError("Transaction broadcasting is disabled")
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        web3 = AsyncWeb3(AsyncHTTPProvider(self.settings.rpc_url(self.chain)))
        if not web3.is_address(destination_address):
            raise ValueError("Invalid EVM destination address")

        configured_address = web3.to_checksum_address(self.settings.wallet_address(self.chain))
        private_key = self.settings.private_key(self.chain).get_secret_value()
        account = web3.eth.account.from_key(private_key)
        if account.address != configured_address:
            raise ValueError("Configured private key does not match wallet address")

        chain_id = await web3.eth.chain_id
        if chain_id != self.expected_chain_id:
            raise NetworkGuardError("RPC chain identity changed before transaction signing")

        nonce = await web3.eth.get_transaction_count(configured_address, "pending")
        transaction = {
            "chainId": chain_id,
            "nonce": nonce,
            "to": web3.to_checksum_address(destination_address),
            "value": web3.to_wei(amount, "ether"),
            "gas": 21000,
            "gasPrice": await web3.eth.gas_price,
        }
        signed = account.sign_transaction(transaction)
        tx_hash = await web3.eth.send_raw_transaction(signed.raw_transaction)
        return ChainTransferResult(tx_hash=tx_hash.hex(), chain=self.chain)

