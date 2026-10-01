"""Chain watchers: detect confirmed native-coin deposits and hand them to DepositService.

Only reads public chain data. No private key is used or needed here.
Limitations: native ETH/BNB/SOL only. ERC-20/SPL tokens and contract-internal
EVM transfers need log/trace scanning and are not detected.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

import httpx
from web3 import AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware

from app.services.deposit_service import DepositService, IncomingTransfer

logger = logging.getLogger(__name__)

WEI = Decimal(10) ** 18
LAMPORTS = Decimal(10) ** 9


def _hex(value) -> str:
    text = value.hex() if hasattr(value, "hex") else str(value)
    return text if text.startswith("0x") else "0x" + text


class EvmWatcher:
    """Scans blocks that are `confirmations` deep, so reorgs cannot create phantom deposits."""

    def __init__(
        self,
        *,
        chain: str,
        rpc_url: str,
        service: DepositService,
        confirmations: int,
        poa: bool = False,
        poll_seconds: float = 6.0,
        max_blocks_per_tick: int = 25,
    ) -> None:
        self.chain = chain
        self.service = service
        self.confirmations = confirmations
        self.poll_seconds = poll_seconds
        self.max_blocks = max_blocks_per_tick
        self.cursor_key = f"evm:{chain}:block"
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        if poa:  # BNB Smart Chain
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("%s watcher tick failed; will retry", self.chain)
            await asyncio.sleep(self.poll_seconds)

    async def tick(self) -> None:
        target = await self.w3.eth.block_number - self.confirmations
        raw = await self.service.get_cursor(self.cursor_key)
        if raw is None:  # first run: start from now, do not replay history
            await self.service.set_cursor(self.cursor_key, str(target))
            return
        cursor = int(raw)
        if target <= cursor:
            return

        addresses = await self.service.watched_addresses(self.chain)
        for number in range(cursor + 1, min(target, cursor + self.max_blocks) + 1):
            if addresses:
                block = await self.w3.eth.get_block(number, full_transactions=True)
                for tx in block["transactions"]:
                    to = tx.get("to")
                    if not to or tx["value"] <= 0 or to.lower() not in addresses:
                        continue
                    receipt = await self.w3.eth.get_transaction_receipt(tx["hash"])
                    if receipt["status"] != 1:  # reverted: no funds moved
                        continue
                    await self.service.handle(
                        IncomingTransfer(
                            chain=self.chain,
                            address=to,
                            amount=Decimal(tx["value"]) / WEI,
                            tx_hash=_hex(tx["hash"]),
                            block_number=number,
                        )
                    )
            await self.service.set_cursor(self.cursor_key, str(number))


class SolanaWatcher:
    """Polls finalized signatures per deposit address and credits SOL balance increases."""

    chain = "solana"

    def __init__(self, *, rpc_url: str, service: DepositService, poll_seconds: float = 8.0) -> None:
        self.service = service
        self.poll_seconds = poll_seconds
        self.http = httpx.AsyncClient(base_url=rpc_url, timeout=20)

    async def _rpc(self, method: str, params: list):
        r = await self.http.post("", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(body["error"])
        return body["result"]

    async def run(self) -> None:
        try:
            while True:
                try:
                    for address in await self.service.watched_addresses(self.chain):
                        await self.check_address(address)
                except Exception:
                    logger.exception("solana watcher tick failed; will retry")
                await asyncio.sleep(self.poll_seconds)
        finally:
            await self.http.aclose()

    async def check_address(self, address: str) -> None:
        key = f"sol:{address}:sig"
        last_sig = await self.service.get_cursor(key)
        opts: dict = {"limit": 50, "commitment": "finalized"}
        if last_sig:
            opts["until"] = last_sig
        sigs = await self._rpc("getSignaturesForAddress", [address, opts])
        if not sigs:
            return
        if last_sig is None:  # first sight of this address: start from now
            await self.service.set_cursor(key, sigs[0]["signature"])
            return
        for entry in reversed(sigs):  # oldest first
            if entry.get("err") is None:
                await self._process(address, entry["signature"], entry.get("slot"))
            await self.service.set_cursor(key, entry["signature"])

    async def _process(self, address: str, signature: str, slot: int | None) -> None:
        tx = await self._rpc(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0, "commitment": "finalized"}],
        )
        if not tx or tx["meta"].get("err") is not None:
            return
        meta = tx["meta"]
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
        loaded = meta.get("loadedAddresses") or {}
        keys += loaded.get("writable", []) + loaded.get("readonly", [])
        if address not in keys:
            return
        i = keys.index(address)
        delta = meta["postBalances"][i] - meta["preBalances"][i]
        if delta > 0:
            await self.service.handle(
                IncomingTransfer(
                    chain=self.chain, address=address, amount=Decimal(delta) / LAMPORTS,
                    tx_hash=signature, block_number=slot,
                )
            )
