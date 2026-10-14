"""Read-only BingX public market-data client.

This client deliberately has no credentials and no order methods. Public prices
remain observable while execution stays MOCK or fail-closed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import BaseModel


class BingXMarketDataError(RuntimeError):
    """Secret-safe public market-data failure."""


class BingXPublicPrice(BaseModel):
    symbol: str
    price: Decimal


class BingXPublicMarketClient:
    PRICE_PATH = "/openApi/swap/v2/quote/price"

    def __init__(self, base_url: str, *, timeout_seconds: int = 10, http: httpx.AsyncClient | None = None) -> None:
        if base_url.rstrip("/") != "https://open-api.bingx.com":
            raise ValueError("public BingX market-data URL is not allowlisted")
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(
            timeout=timeout_seconds, limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        self._owns_http = http is None
        self.last_success_at: datetime | None = None
        self.last_error_at: datetime | None = None

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    @staticmethod
    def _parse(data: Any, requested_symbols: frozenset[str]) -> list[BingXPublicPrice]:
        items = data if isinstance(data, list) else [data]
        if not all(isinstance(item, dict) for item in items):
            raise BingXMarketDataError("BingX returned malformed public market data")
        prices: list[BingXPublicPrice] = []
        for item in items:
            symbol = str(item.get("symbol", ""))
            if symbol not in requested_symbols:
                continue
            try:
                price = Decimal(str(item.get("price")))
            except (InvalidOperation, ValueError) as exc:
                raise BingXMarketDataError("BingX returned an invalid public price") from exc
            if not price.is_finite() or price <= 0:
                raise BingXMarketDataError("BingX returned an invalid public price")
            prices.append(BingXPublicPrice(symbol=symbol, price=price))
        found = {price.symbol for price in prices}
        if found != requested_symbols:
            raise BingXMarketDataError("BingX public market response omitted a requested symbol")
        return sorted(prices, key=lambda value: value.symbol)

    async def prices(self, symbols: tuple[str, ...]) -> list[BingXPublicPrice]:
        requested = frozenset(symbols)
        if not requested or any(not symbol or len(symbol) > 30 for symbol in requested):
            raise ValueError("at least one valid market symbol is required")
        try:
            response = await self._http.get(f"{self.base_url}{self.PRICE_PATH}")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or str(payload.get("code")) != "0" or "data" not in payload:
                raise BingXMarketDataError("BingX rejected the public market-data request")
            prices = self._parse(payload["data"], requested)
        except (BingXMarketDataError, httpx.HTTPError, ValueError) as exc:
            self.last_error_at = datetime.now(UTC)
            if isinstance(exc, BingXMarketDataError):
                raise
            raise BingXMarketDataError("BingX public market data is unavailable") from exc
        self.last_success_at = datetime.now(UTC)
        return prices
