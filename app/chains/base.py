from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.security.network_guard import NetworkGuard


@dataclass(frozen=True)
class ChainTransferResult:
    tx_hash: str
    chain: str


class BaseChainAdapter(ABC):
    chain: str
    asset: str

    def __init__(self, network_guard: NetworkGuard) -> None:
        self.network_guard = network_guard

    async def assert_ready(self) -> None:
        self.network_guard.assert_network(self.chain)
        await self.network_guard.verify_rpc(self.chain)

    @abstractmethod
    async def broadcast_native_transfer(
        self, destination_address: str, amount: Decimal
    ) -> ChainTransferResult:
        raise NotImplementedError
