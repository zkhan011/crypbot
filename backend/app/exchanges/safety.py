"""Exchange-neutral preflight validation and market-data freshness controls."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN

from app.domain.types import Side
from app.exchanges.interfaces import OrderRequest, SymbolMetadata


class OrderValidationError(ValueError):
    """An order cannot be normalized without violating exchange or risk rules."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class OrderValidationResult:
    requested_quantity: Decimal
    normalized_quantity: Decimal
    requested_price: Decimal | None
    normalized_price: Decimal | None
    notional: Decimal | None

    @property
    def changed(self) -> bool:
        return self.requested_quantity != self.normalized_quantity or self.requested_price != self.normalized_price


class OrderValidationService:
    """Normalizes only toward lower exposure and validates the resulting order."""

    @staticmethod
    def _quantity_down(value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

    @staticmethod
    def _price_risk_safe(value: Decimal, tick: Decimal, side: Side) -> Decimal:
        rounding = ROUND_DOWN if side == Side.BUY else ROUND_CEILING
        return (value / tick).to_integral_value(rounding=rounding) * tick

    def validate_and_normalize(
        self,
        request: OrderRequest,
        rules: SymbolMetadata,
        *,
        reference_price: Decimal | None = None,
    ) -> tuple[OrderRequest, OrderValidationResult]:
        if request.symbol != rules.symbol:
            raise OrderValidationError("SYMBOL_MISMATCH", "order symbol does not match loaded trading rules")
        if request.quantity <= 0:
            raise OrderValidationError("INVALID_QUANTITY", "order quantity must be positive")
        if rules.quantity_step <= 0 or rules.tick_size <= 0:
            raise OrderValidationError("INVALID_TRADING_RULES", "exchange returned invalid precision rules")

        quantity = self._quantity_down(request.quantity, rules.quantity_step)
        if quantity < rules.min_quantity:
            raise OrderValidationError("MIN_QUANTITY", "normalized quantity is below the exchange minimum")

        price = request.price
        if price is not None:
            if price <= 0:
                raise OrderValidationError("INVALID_PRICE", "order price must be positive")
            price = self._price_risk_safe(price, rules.tick_size, request.side)
            if price <= 0:
                raise OrderValidationError("INVALID_PRICE", "normalized price must be positive")

        trigger_price = request.trigger_price
        if trigger_price is not None:
            if trigger_price <= 0:
                raise OrderValidationError("INVALID_TRIGGER_PRICE", "trigger price must be positive")
            trigger_price = self._price_risk_safe(trigger_price, rules.tick_size, request.side)

        valuation_price = price or reference_price
        order_notional = quantity * valuation_price if valuation_price is not None else None
        if rules.min_notional > 0 and order_notional is None:
            raise OrderValidationError("REFERENCE_PRICE_REQUIRED", "reference price is required for notional validation")
        if order_notional is not None and order_notional < rules.min_notional:
            raise OrderValidationError("MIN_NOTIONAL", "normalized order notional is below the exchange minimum")

        normalized = request.model_copy(update={"quantity": quantity, "price": price, "trigger_price": trigger_price})
        return normalized, OrderValidationResult(
            requested_quantity=request.quantity,
            normalized_quantity=quantity,
            requested_price=request.price,
            normalized_price=price,
            notional=order_notional,
        )


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    observed_monotonic: Decimal
    last_price: Decimal | None = None
    mark_price: Decimal | None = None
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    funding_rate: Decimal | None = None
    contract_active: bool | None = None
    order_book_exchange_timestamp: int | None = None


class StaleMarketDataError(RuntimeError):
    pass


class MarketDataCache:
    """Async-safe process-local snapshot cache; Redis coordination remains a runtime concern."""

    def __init__(self, stale_after_seconds: Decimal = Decimal("5")) -> None:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self.stale_after_seconds = stale_after_seconds
        self._snapshots: dict[str, MarketSnapshot] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _now() -> Decimal:
        return Decimal(str(time.monotonic()))

    async def update(self, symbol: str, **values: Decimal | bool | int | None) -> MarketSnapshot:
        async with self._lock:
            current = self._snapshots.get(symbol, MarketSnapshot(symbol=symbol, observed_monotonic=self._now()))
            snapshot = replace(current, observed_monotonic=self._now(), **values)
            self._snapshots[symbol] = snapshot
            return snapshot

    async def require_fresh(self, symbol: str) -> MarketSnapshot:
        async with self._lock:
            snapshot = self._snapshots.get(symbol)
            if snapshot is None:
                raise StaleMarketDataError("required market data is unavailable")
            if self._now() - snapshot.observed_monotonic > self.stale_after_seconds:
                raise StaleMarketDataError("required market data is stale")
            return snapshot
