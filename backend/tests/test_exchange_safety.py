from decimal import Decimal

import pytest

from app.domain.trading_types import OrderType, Side
from app.exchanges.interfaces import OrderRequest, SymbolMetadata
from app.exchanges.safety import (
    MarketDataCache,
    OrderValidationError,
    OrderValidationService,
    StaleMarketDataError,
    TradingRulesCache,
)


def rules() -> SymbolMetadata:
    return SymbolMetadata(
        symbol="BTC-USDT",
        min_quantity=Decimal("0.001"),
        quantity_step=Decimal("0.001"),
        tick_size=Decimal("0.1"),
        min_notional=Decimal("5"),
    )


def test_order_normalization_never_increases_quantity_or_buy_price() -> None:
    request = OrderRequest(
        account_id="account",
        symbol="BTC-USDT",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.0019"),
        price=Decimal("61000.19"),
        client_order_id="idempotent-id",
    )
    normalized, decision = OrderValidationService().validate_and_normalize(request, rules())
    assert normalized.quantity == Decimal("0.001")
    assert normalized.price == Decimal("61000.1")
    assert decision.changed
    assert decision.notional == Decimal("61.0001")


def test_sell_price_rounds_up_without_increasing_quantity() -> None:
    request = OrderRequest(
        account_id="account",
        symbol="BTC-USDT",
        side=Side.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.0029"),
        price=Decimal("61000.11"),
        client_order_id="idempotent-id",
    )
    normalized, _ = OrderValidationService().validate_and_normalize(request, rules())
    assert normalized.quantity == Decimal("0.002")
    assert normalized.price == Decimal("61000.2")


def test_normalization_rejects_below_minimum() -> None:
    request = OrderRequest(
        account_id="account",
        symbol="BTC-USDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.0009"),
        client_order_id="idempotent-id",
    )
    with pytest.raises(OrderValidationError) as captured:
        OrderValidationService().validate_and_normalize(request, rules(), reference_price=Decimal("61000"))
    assert captured.value.reason_code == "MIN_QUANTITY"


@pytest.mark.asyncio
async def test_market_cache_blocks_missing_and_stale_data() -> None:
    cache = MarketDataCache(stale_after_seconds=Decimal("0.000001"))
    with pytest.raises(StaleMarketDataError):
        await cache.require_fresh("BTC-USDT")
    await cache.update("BTC-USDT", last_price=Decimal("61000"))
    with pytest.raises(StaleMarketDataError):
        await cache.require_fresh("BTC-USDT")


@pytest.mark.asyncio
async def test_market_cache_returns_fresh_decimal_snapshot() -> None:
    cache = MarketDataCache(stale_after_seconds=Decimal("5"))
    await cache.update("BTC-USDT", last_price=Decimal("61000.25"), best_bid=Decimal("61000.1"))
    snapshot = await cache.require_fresh("BTC-USDT")
    assert snapshot.last_price == Decimal("61000.25")
    assert snapshot.best_bid == Decimal("61000.1")


@pytest.mark.asyncio
async def test_trading_rules_cache_reuses_and_force_refreshes() -> None:
    calls = 0

    async def loader(symbol: str) -> SymbolMetadata:
        nonlocal calls
        calls += 1
        return rules()

    cache = TradingRulesCache(Decimal("900"))
    await cache.get("BTC-USDT", loader)
    await cache.get("BTC-USDT", loader)
    assert calls == 1
    cache.invalidate("BTC-USDT")
    await cache.get("BTC-USDT", loader)
    assert calls == 2
