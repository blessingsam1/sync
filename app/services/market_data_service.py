from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic

import httpx


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: Decimal
    change_percent: Decimal
    source: str
    observed_at: datetime


class SimulatedMarketDataService:
    async def quotes(self) -> list[MarketQuote]:
        now = datetime.now(UTC)
        return [
            MarketQuote("SOL/USDC", Decimal("142.50"), Decimal("1.25"), "simulation", now),
            MarketQuote("ETH/USDC", Decimal("3250.00"), Decimal("-0.40"), "simulation", now),
            MarketQuote("BNB/USDC", Decimal("610.00"), Decimal("0.75"), "simulation", now),
        ]


class LiveMarketDataService:
    URL = "https://api.coingecko.com/api/v3/simple/price"
    COIN_IDS = {"SOL": "solana", "ETH": "ethereum", "BNB": "binancecoin"}

    def __init__(self, cache_seconds: int = 60) -> None:
        self.cache_seconds = cache_seconds
        self._cached_prices: dict[str, Decimal] | None = None
        self._cached_at = 0.0

    async def usd_prices(self) -> dict[str, Decimal] | None:
        now = monotonic()
        if self._cached_prices is not None and now - self._cached_at < self.cache_seconds:
            return self._cached_prices
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.URL,
                    params={"ids": ",".join(self.COIN_IDS.values()), "vs_currencies": "usd"},
                )
                response.raise_for_status()
                payload = response.json()
            prices = {
                symbol: Decimal(str(payload[coin_id]["usd"]))
                for symbol, coin_id in self.COIN_IDS.items()
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return self._cached_prices
        self._cached_prices = prices
        self._cached_at = now
        return prices
