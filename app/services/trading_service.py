from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chains.base import BaseChainAdapter
from app.database.models import Transaction
from app.schemas.transaction import NativeTransferRequest
from app.security.network_guard import NetworkGuard

logger = logging.getLogger(__name__)


class TradingService:
    def __init__(
        self,
        session: AsyncSession,
        network_guard: NetworkGuard,
        adapters: dict[str, BaseChainAdapter],
        execution_enabled: bool,
    ) -> None:
        self.session = session
        self.network_guard = network_guard
        self.adapters = adapters
        self.execution_enabled = execution_enabled

    async def native_transfer(self, request: NativeTransferRequest) -> Transaction:
        self.network_guard.assert_network(request.chain)
        existing = await self.session.scalar(
            select(Transaction).where(
                Transaction.idempotency_key == request.idempotency_key
            )
        )
        if existing is not None:
            return existing

        transaction = Transaction(
            user_id=request.user_id,
            idempotency_key=request.idempotency_key,
            chain=request.chain,
            asset=request.asset.upper(),
            transaction_type="native_transfer",
            amount=request.amount,
            destination_address=request.destination_address,
            status="created",
        )
        self.session.add(transaction)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raced_transaction = await self.session.scalar(
                select(Transaction).where(
                    Transaction.idempotency_key == request.idempotency_key
                )
            )
            if raced_transaction is None:
                raise
            return raced_transaction
        await self.session.refresh(transaction)

        if not self.execution_enabled:
            transaction.status = "simulated"
            await self.session.commit()
            return transaction

        adapter = self.adapters.get(request.chain)
        if adapter is None:
            transaction.status = "rejected"
            transaction.error_code = "ADAPTER_NOT_CONFIGURED"
            await self.session.commit()
            return transaction

        try:
            result = await adapter.broadcast_native_transfer(
                request.destination_address, request.amount
            )
        except Exception as exc:
            transaction.status = "failed"
            transaction.error_code = type(exc).__name__[:64]
            await self.session.commit()
            logger.exception(
                "Mainnet transaction failed",
                extra={"transaction_id": transaction.id, "chain": request.chain},
            )
            return transaction

        transaction.status = "broadcast"
        transaction.tx_hash = result.tx_hash
        await self.session.commit()
        return transaction
