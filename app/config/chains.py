from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChainDefinition:
    key: str
    display_name: str
    asset: str
    expected_chain_id: int | None = None
    expected_genesis_hash: str | None = None


ETHEREUM_MAINNET = ChainDefinition(
    key="ethereum",
    display_name="Ethereum Mainnet",
    asset="ETH",
    expected_chain_id=1,
)

BNB_MAINNET = ChainDefinition(
    key="bnb",
    display_name="BNB Smart Chain Mainnet",
    asset="BNB",
    expected_chain_id=56,
)

SOLANA_MAINNET = ChainDefinition(
    key="solana",
    display_name="Solana Mainnet",
    asset="SOL",
    expected_genesis_hash="5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d",
)

APPROVED_CHAINS = {
    ETHEREUM_MAINNET.key: ETHEREUM_MAINNET,
    BNB_MAINNET.key: BNB_MAINNET,
    SOLANA_MAINNET.key: SOLANA_MAINNET,
}

ASSET_TO_CHAIN = {definition.asset: definition.key for definition in APPROVED_CHAINS.values()}
