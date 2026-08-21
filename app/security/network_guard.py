from __future__ import annotations

import asyncio

import httpx

from app.config.chains import APPROVED_CHAINS
from app.config.settings import Settings


class NetworkGuardError(RuntimeError):
    pass


class NetworkGuard:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        startup_retry_attempts: int = 3,
        startup_retry_delay: float = 1.0,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.startup_retry_attempts = max(1, startup_retry_attempts)
        self.startup_retry_delay = max(0.0, startup_retry_delay)
        if settings.network_mode != "mainnet":
            raise NetworkGuardError("Application is not in mainnet mode")

    def assert_network(self, chain: str) -> None:
        if self.settings.network_mode != "mainnet":
            raise NetworkGuardError("NETWORK_MODE must be mainnet")
        if chain not in APPROVED_CHAINS:
            raise NetworkGuardError(f"Unsupported mainnet chain: {chain}")
        rpc_url = self.settings.rpc_url(chain)
        if not rpc_url:
            raise NetworkGuardError(f"Missing mainnet RPC URL for {chain}")

    async def verify_all(self) -> None:
        for chain in APPROVED_CHAINS:
            await self._verify_rpc_with_retries(chain)

    async def _verify_rpc_with_retries(self, chain: str) -> None:
        for attempt in range(self.startup_retry_attempts):
            try:
                await self.verify_rpc(chain)
                return
            except NetworkGuardError as exc:
                is_transient = exc.__cause__ is not None
                is_last_attempt = attempt == self.startup_retry_attempts - 1
                if not is_transient or is_last_attempt:
                    raise
                delay = self.startup_retry_delay * (2**attempt)
                if delay:
                    await asyncio.sleep(delay)

    async def verify_rpc(self, chain: str) -> None:
        self.assert_network(chain)
        definition = APPROVED_CHAINS[chain]
        rpc_url = self.settings.rpc_url(chain)
        method = "getGenesisHash" if chain == "solana" else "eth_chainId"
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": []}
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self.transport) as client:
                response = await client.post(rpc_url, json=payload)
                response.raise_for_status()
                result = response.json().get("result")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise NetworkGuardError(f"Could not verify {chain} mainnet RPC") from exc

        if chain == "solana":
            if result != definition.expected_genesis_hash:
                raise NetworkGuardError("Solana RPC is not the approved Mainnet cluster")
            return

        try:
            chain_id = int(result, 16)
        except (TypeError, ValueError) as exc:
            raise NetworkGuardError(f"Invalid chain ID response for {chain}") from exc
        if chain_id != definition.expected_chain_id:
            raise NetworkGuardError(
                f"{chain} RPC returned chain ID {chain_id}; "
                f"expected {definition.expected_chain_id}"
            )
