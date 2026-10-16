import gzip
import json
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest

from app.domain.trading_types import OrderStatus, OrderType, PositionSide, Side, TimeInForce
from app.exchanges.bingx import (
    BingXClient,
    BingXInsufficientBalanceError,
    BingXInvalidLeverageError,
    BingXInvalidParameterError,
    BingXLiveGates,
    BingXOrderNotFoundError,
    BingXPositionLimitError,
    BingXRateLimitError,
    BingXRiskRestrictionError,
    BingXUnsupportedSymbolError,
)
from app.exchanges.bingx_websocket import BingXWebSocketClient, BingXWebSocketDisabled, WebSocketState
from app.exchanges.interfaces import Fill, OrderRequest, OrderResult, Position
from app.services.copy import CopyEventDeduplicator, CopySizingMode, CopySizingRequest, CopySizingService
from app.services.execution_safety import (
    CancellationRatioGuard,
    ControlledOrder,
    FillVolumeLedger,
    SelfTradePreventionError,
    SelfTradePreventionService,
    VolumeExecutionRiskService,
    VolumeOrderContext,
    VolumeSafetyLimits,
    spread_bps,
)
from app.services.reconciliation import StartupReconciliationService


def envelope(request: httpx.Request, data: object, code: int = 0, msg: str = "") -> httpx.Response:
    return httpx.Response(200, request=request, json={"code": code, "msg": msg, "timestamp": 1_700_000_000_000, "data": data})


def gates() -> BingXLiveGates:
    return BingXLiveGates(True, True, True, True, True)


def contract_data() -> list[dict[str, object]]:
    return [
        {
            "symbol": "BTC-USDT",
            "minQty": "0.001",
            "maxQty": "10",
            "quantityPrecision": 3,
            "pricePrecision": 1,
            "tradeMinUSDT": "5",
            "status": "TRADING",
        }
    ]


@pytest.mark.asyncio
async def test_timestamp_rejection_resynchronizes_once_and_retries_signed_read() -> None:
    balance_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal balance_calls
        if request.url.path.endswith("/server/time"):
            return envelope(request, {"serverTime": 1_100})
        balance_calls += 1
        if balance_calls == 1:
            return envelope(request, {}, 90001, "timestamp outside recvWindow")
        assert parse_qs(request.url.query.decode())["timestamp"] == ["1100"]
        return envelope(request, {"balance": {"asset": "USDT", "balance": "10", "availableMargin": "9"}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "test-key", "test-secret", http=http, clock_ms=lambda: 1_000)
    assert (await client.balances("internal"))[0].available == Decimal("9")
    assert balance_calls == 2
    await http.aclose()


@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        (101206, BingXInsufficientBalanceError),
        (101209, BingXPositionLimitError),
        (101414, BingXInvalidLeverageError),
        (109403, BingXRiskRestrictionError),
        (109421, BingXOrderNotFoundError),
        (109425, BingXUnsupportedSymbolError),
        (109429, BingXRateLimitError),
        (110400, BingXInvalidParameterError),
    ],
)
@pytest.mark.asyncio
async def test_known_error_code_mapping(code: int, error_type: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return envelope(request, {}, code, "exchange detail is intentionally not reflected")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "test-key", "test-secret", http=http, max_retries=0)
    with pytest.raises(error_type):
        await client.price("BTC-USDT")
    await http.aclose()


@pytest.mark.asyncio
async def test_market_account_and_position_parsers_use_decimal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/premiumIndex"):
            return envelope(
                request,
                {"symbol": "BTC-USDT", "markPrice": "61000.1", "indexPrice": "60999.9", "lastFundingRate": "0.0001", "nextFundingTime": 9},
            )
        if path.endswith("/fundingRate"):
            return envelope(request, [{"symbol": "BTC-USDT", "fundingRate": "0.0002", "fundingTime": 8}])
        if path.endswith("/openInterest"):
            return envelope(request, {"symbol": "BTC-USDT", "openInterest": "123.45"})
        if path.endswith("/bookTicker"):
            return envelope(request, {"symbol": "BTC-USDT", "bidPrice": "61000", "askPrice": "61001"})
        if path.endswith("/commissionRate"):
            return envelope(request, {"makerCommissionRate": "0.0002", "takerCommissionRate": "0.0005"})
        if path.endswith("/positions"):
            return envelope(
                request,
                [
                    {
                        "positionId": "position-1",
                        "symbol": "BTC-USDT",
                        "positionSide": "LONG",
                        "positionAmt": "0.1",
                        "availableAmt": "0.08",
                        "avgPrice": "60000",
                        "markPrice": "61000",
                        "leverage": "2",
                        "marginType": "ISOLATED",
                        "liquidationPrice": "30000",
                        "unrealizedProfit": "100",
                        "realizedPnl": "10",
                        "updateTime": 7,
                    }
                ],
            )
        raise AssertionError(path)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "test-key", "test-secret", http=http)
    premium = (await client.premium_index("BTC-USDT"))[0]
    assert premium.mark_price == Decimal("61000.1")
    assert (await client.funding_rates("BTC-USDT"))[0].funding_rate == Decimal("0.0002")
    assert await client.open_interest("BTC-USDT") == Decimal("123.45")
    assert await client.best_bid_ask("BTC-USDT") == (Decimal("61000"), Decimal("61001"))
    assert (await client.commission_rate("BTC-USDT")).taker_rate == Decimal("0.0005")
    position = (await client.positions("internal"))[0]
    assert position.position_id == "position-1"
    assert position.unrealized_pnl == Decimal("100")
    assert position.available_quantity == Decimal("0.08")
    await http.aclose()


def test_order_parameter_construction_only_sends_applicable_fields() -> None:
    client = BingXClient("https://open-api.bingx.com", "test-key", "test-secret")
    market = client._order_params(
        OrderRequest(
            account_id="a",
            symbol="BTC-USDT",
            side=Side.BUY,
            position_side=PositionSide.LONG,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
            client_order_id="id",
        )
    )
    assert market == {
        "symbol": "BTC-USDT",
        "side": "BUY",
        "positionSide": "LONG",
        "type": "MARKET",
        "quantity": "0.01",
        "clientOrderID": "id",
    }
    limit = client._order_params(
        OrderRequest(
            account_id="a",
            symbol="BTC-USDT",
            side=Side.SELL,
            position_side=PositionSide.LONG,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            price=Decimal("62000"),
            time_in_force=TimeInForce.IOC,
            reduce_only=True,
            client_order_id="id2",
        )
    )
    assert limit["price"] == "62000" and limit["timeInForce"] == "IOC" and limit["reduceOnly"] == "true"
    trailing = client._order_params(
        OrderRequest(
            account_id="a",
            symbol="BTC-USDT",
            side=Side.SELL,
            position_side=PositionSide.LONG,
            order_type=OrderType.TRAILING_STOP_MARKET,
            quantity=Decimal("0.01"),
            trigger_price=Decimal("60000"),
            client_order_id="id3",
        )
    )
    assert trailing["type"] == "TRAILING_STOP_MARKET" and trailing["stopPrice"] == "60000" and "price" not in trailing


@pytest.mark.asyncio
async def test_batch_partial_result_is_not_treated_as_complete_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/contracts"):
            return envelope(request, contract_data())
        if request.url.path.endswith("/price"):
            return envelope(request, {"symbol": "BTC-USDT", "price": "61000"})
        return envelope(request, [{"orderId": "1", "clientOrderID": "one", "status": "NEW"}])

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "test-key", "test-secret", http=http, live_gates=gates())
    requests = [
        OrderRequest(
            account_id="a", symbol="BTC-USDT", side=Side.BUY, order_type=OrderType.MARKET, quantity=Decimal("0.001"), client_order_id=value
        )
        for value in ("one", "two")
    ]
    results = await client.batch_submit_orders(requests)
    assert [result.status for result in results] == [OrderStatus.SUBMITTED, OrderStatus.UNKNOWN]
    assert results[1].reason == "BATCH_CHILD_RESULT_MISSING"
    await http.aclose()


@pytest.mark.asyncio
async def test_explicit_demo_test_order_uses_only_test_endpoint() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/contracts"):
            return envelope(request, contract_data())
        if request.url.path.endswith("/price"):
            return envelope(request, {"symbol": "BTC-USDT", "price": "61000"})
        assert request.url.path.endswith("/order/test")
        return envelope(request, {})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "test-key", "test-secret", http=http, allow_test_orders=True)
    await client.test_order(
        OrderRequest(
            account_id="demo",
            symbol="BTC-USDT",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.001"),
            client_order_id="test-only",
        )
    )
    assert paths[-1] == "/openApi/swap/v2/trade/order/test"
    assert "/openApi/swap/v2/trade/order" not in paths
    await http.aclose()


@pytest.mark.asyncio
async def test_cancel_requires_symbol_before_exchange_mutation() -> None:
    client = BingXClient("https://open-api.bingx.com", "test-key", "test-secret", live_gates=gates())
    with pytest.raises(BingXInvalidParameterError, match="requires symbol"):
        await client.cancel_order("account", "client-id")
    await client.close()


class FakeWebSocket:
    def __init__(self, messages: list[str | bytes]) -> None:
        self.messages = messages
        self.sent: list[str | bytes] = []
        self.closed = False

    async def send(self, message: str | bytes) -> None:
        self.sent.append(message)

    async def recv(self) -> str | bytes:
        return self.messages.pop(0)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_websocket_configurable_subscription_decode_dedupe_and_recovery() -> None:
    event = {"stream": "ticker", "price": "61000"}
    sockets = [FakeWebSocket([gzip.compress(json.dumps(event).encode()), json.dumps(event)]), FakeWebSocket([])]
    recoveries = 0

    async def connector(url: str) -> FakeWebSocket:
        return sockets.pop(0)

    async def recovery() -> None:
        nonlocal recoveries
        recoveries += 1

    async def collect(value: dict[str, object]) -> None:
        received.append(value)

    received: list[dict[str, object]] = []
    client = BingXWebSocketClient(
        "wss://open-api-swap.bingx.com/swap-market",
        subscriptions_enabled=True,
        connector=connector,
        rest_recovery=recovery,
        max_backoff_seconds=Decimal("0.001"),
    )
    await client.connect()
    await client.subscribe("ticker", {"id": "sanitized", "reqType": "sub"}, collect)
    await client.receive_once(lambda value: str(value.get("stream")))
    await client.receive_once(lambda value: str(value.get("stream")))
    assert received == [event]
    await client.reconnect()
    assert recoveries == 1 and client.state == WebSocketState.CONNECTED
    await client.stop()


@pytest.mark.asyncio
async def test_websocket_private_subscription_fails_closed() -> None:
    async def connector(url: str) -> FakeWebSocket:
        return FakeWebSocket([])

    client = BingXWebSocketClient("wss://open-api-swap.bingx.com/swap-market", subscriptions_enabled=True, connector=connector)
    with pytest.raises(BingXWebSocketDisabled):
        await client.subscribe("orders", {"unverified": True}, lambda event: None, private=True)  # type: ignore[arg-type]


def test_fill_volume_fee_self_trade_and_cancellation_controls() -> None:
    ledger = FillVolumeLedger()
    ledger.record(
        Fill(fill_id="1", symbol="BTC-USDT", side=Side.BUY, price=Decimal("100"), quantity=Decimal("2"), fee=Decimal("0.1"), maker=True)
    )
    ledger.record(
        Fill(fill_id="2", symbol="BTC-USDT", side=Side.SELL, price=Decimal("110"), quantity=Decimal("1"), fee=Decimal("0.2"), maker=False)
    )
    assert ledger.buy_volume == Decimal("200") and ledger.sell_volume == Decimal("110")
    assert ledger.gross_volume == Decimal("310") and ledger.net_quantity == Decimal("1")
    assert ledger.maker_fees == Decimal("0.1") and ledger.taker_fees == Decimal("0.2")
    with pytest.raises(SelfTradePreventionError):
        SelfTradePreventionService().validate(
            ControlledOrder("a", "BTC-USDT", Side.BUY, Decimal("101")), [ControlledOrder("b", "BTC-USDT", Side.SELL, Decimal("100"))]
        )
    guard = CancellationRatioGuard(Decimal("0.25"))
    guard.record_submission()
    guard.record_submission()
    guard.record_cancellation()
    assert not guard.allow_opening_order()
    assert spread_bps(Decimal("99"), Decimal("101")) == Decimal("200")

    limits = VolumeSafetyLimits(
        allowed_symbols=frozenset({"BTC-USDT"}),
        maximum_order_quantity=Decimal("1"),
        maximum_order_notional=Decimal("1000"),
        maximum_position_notional=Decimal("2000"),
        maximum_daily_loss=Decimal("100"),
        maximum_fee_budget=Decimal("10"),
        maximum_spread_bps=Decimal("25"),
        maximum_slippage_bps=Decimal("20"),
        minimum_depth_notional=Decimal("5000"),
        volatility_limit=Decimal("0.05"),
    )
    safe_guard = CancellationRatioGuard(Decimal("0.5"))
    context = VolumeOrderContext(
        symbol="BTC-USDT",
        quantity=Decimal("0.1"),
        price=Decimal("100"),
        resulting_position_notional=Decimal("100"),
        daily_loss=Decimal("0"),
        fees_used=Decimal("0"),
        spread_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
        depth_notional=Decimal("10000"),
        volatility=Decimal("0.01"),
        market_data_fresh=True,
    )
    VolumeExecutionRiskService().validate(context, limits, safe_guard)
    with pytest.raises(ValueError, match="stale"):
        VolumeExecutionRiskService().validate(VolumeOrderContext(**{**context.__dict__, "market_data_fresh": False}), limits, safe_guard)


def test_copy_sizing_modes_and_deduplication() -> None:
    service = CopySizingService()
    base = dict(price=Decimal("100"), follower_balance=Decimal("1000"), leader_quantity=Decimal("2"), leader_equity=Decimal("2000"))
    assert service.calculate(
        CopySizingRequest(mode=CopySizingMode.FIXED_USDT, fixed_usdt=Decimal("50"), **base), Decimal("0.01")
    ) == Decimal("0.5")
    assert service.calculate(
        CopySizingRequest(mode=CopySizingMode.BALANCE_PERCENTAGE, balance_percentage=Decimal("0.1"), **base), Decimal("0.01")
    ) == Decimal("1")
    dedupe = CopyEventDeduplicator()
    assert dedupe.accept("source-1") and not dedupe.accept("source-1")


@pytest.mark.asyncio
async def test_startup_reconciliation_blocks_unknown_state() -> None:
    class Exchange:
        async def open_orders(self, symbol=None):
            return [OrderResult(client_order_id="known", exchange_order_id="1", status=OrderStatus.SUBMITTED)]

        async def order_history(self, symbol=None, **kwargs):
            return []

        async def fills(self, symbol=None, **kwargs):
            return []

        async def positions(self, account_id, symbol=None):
            return [
                Position(
                    symbol="BTC-USDT",
                    side=Side.BUY,
                    quantity=Decimal("1"),
                    entry_price=Decimal("100"),
                    leverage=Decimal("1"),
                    position_id="unknown-position",
                )
            ]

    result = await StartupReconciliationService().reconcile(Exchange(), "account", {"known"}, set())
    assert not result.ready_for_opening
    assert result.incidents[0].category == "Unknown exchange position"
