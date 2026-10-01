from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic

import httpx

logger = logging.getLogger(__name__)


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
    COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
    BINANCE_URL = "https://data-api.binance.vision/api/v3/ticker/price"

    COIN_IDS = {"SOL": "solana", "ETH": "ethereum", "BNB": "binancecoin"}
    BINANCE_SYMBOLS = {"SOL": "SOLUSDT", "ETH": "ETHUSDT", "BNB": "BNBUSDT"}

    def __init__(self, cache_seconds: int = 60, failure_backoff: int = 30) -> None:
        self.cache_seconds = cache_seconds
        self.failure_backoff = failure_backoff
        self._cached_prices: dict[str, Decimal] | None = None
        self._cached_at = 0.0
        self._retry_after = 0.0

        self._cg_headers = {
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; TradeSyncBot/1.0)",
        }
        key = os.getenv("COINGECKO_API_KEY")
        if key:
            self._cg_headers["x-cg-demo-api-key"] = key

    async def usd_prices(self) -> dict[str, Decimal] | None:
        now = monotonic()
        if self._cached_prices is not None and now - self._cached_at < self.cache_seconds:
            return self._cached_prices
        if now < self._retry_after:
            return self._cached_prices

        prices = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, fetch in (
                ("binance", self._fetch_binance),
                ("coingecko", self._fetch_coingecko),
            ):
                try:
                    prices = await fetch(client)
                    if prices:
                        logger.info("Fetched USD prices from %s: %s", name, prices)
                        break
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "%s HTTP %s: %s",
                        name,
                        exc.response.status_code,
                        exc.response.text[:200].replace("\n", " "),
                    )
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    logger.warning("%s failed: %r", name, exc)

        if not prices:
            logger.error("All price providers failed; backing off %ss", self.failure_backoff)
            self._retry_after = now + self.failure_backoff
            return self._cached_prices

        self._cached_prices = prices
        self._cached_at = now
        return prices

    async def _fetch_coingecko(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        r = await client.get(
            self.COINGECKO_URL,
            params={"ids": ",".join(self.COIN_IDS.values()), "vs_currencies": "usd"},
            headers=self._cg_headers,
        )
        r.raise_for_status()
        data = r.json()
        return {
            sym: Decimal(str(data[cid]["usd"]))
            for sym, cid in self.COIN_IDS.items()
            if cid in data and "usd" in data[cid]
        }

    async def _fetch_binance(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        symbols = list(self.BINANCE_SYMBOLS.values())
        r = await client.get(
            self.BINANCE_URL,
            params={"symbols": json.dumps(symbols, separators=(",", ":"))},
        )
        r.raise_for_status()
        by_pair = {row["symbol"]: Decimal(row["price"]) for row in r.json()}
        return {
            sym: by_pair[pair]
            for sym, pair in self.BINANCE_SYMBOLS.items()
            if pair in by_pair
        }