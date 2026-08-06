from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest

from app.domain.types import OrderStatus, OrderType, Side
from app.exchanges.bingx import BingXClient, BingXError, BingXLiveGates, BingXLiveTradingDisabled, BingXSigner
from app.exchanges.interfaces import OrderRequest


def response(request: httpx.Request, data: object, code: int = 0) -> httpx.Response:
    return httpx.Response(200, request=request, json={"code": code, "msg": "", "data": data})


def all_live_gates() -> BingXLiveGates:
    return BingXLiveGates(
        environment_enabled=True,
        credential_verified=True,
        strategy_approved=True,
        risk_configured=True,
        final_confirmation=True,
    )


def preflight_response(request: httpx.Request) -> httpx.Response | None:
    if request.url.path.endswith("/contracts"):
        return response(
            request,
            [
                {
                    "symbol": "BTC-USDT",
                    "minQty": "0.001",
                    "quantityPrecision": 3,
                    "pricePrecision": 1,
                    "tradeMinUSDT": "5",
                }
            ],
        )
    if request.url.path.endswith("/price"):
        return response(request, {"symbol": "BTC-USDT", "price": "61000"})
    return None


@pytest.mark.asyncio
async def test_public_market_data_uses_decimal_and_no_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "X-BX-APIKEY" not in request.headers
        if request.url.path.endswith("/contracts"):
            return response(
                request,
                [
                    {
                        "symbol": "BTC-USDT",
                        "minQty": "0.001",
                        "quantityPrecision": 3,
                        "pricePrecision": 1,
                        "tradeMinUSDT": "5",
                    }
                ],
            )
        if request.url.path.endswith("/price"):
            return response(request, {"symbol": "BTC-USDT", "price": "61234.50"})
        if request.url.path.endswith("/klines"):
            return response(request, [[1_700_000_000_000, "60000", "62000", "59000", "61000", "123.45"]])
        return response(request, {"bids": [["61000", "1.2"]], "asks": [["61001", "0.8"]], "T": 1_700_000_000_001})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "masked-test-key", "test-secret", http=http)

    metadata = await client.symbol_metadata("BTC-USDT")
    assert metadata.quantity_step == Decimal("0.001")
    assert metadata.tick_size == Decimal("0.1")
    assert await client.price("BTC-USDT") == Decimal("61234.50")
    assert (await client.candles("BTC-USDT", "1m", 1))[0].volume == Decimal("123.45")
    book = await client.order_book("BTC-USDT", 20)
    assert book.bids[0].quantity == Decimal("1.2")
    await http.aclose()


@pytest.mark.asyncio
async def test_private_request_is_signed_without_transmitting_internal_account_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        preflight = preflight_response(request)
        if preflight is not None:
            return preflight
        query = parse_qs(request.url.query.decode())
        assert request.headers["X-BX-APIKEY"] == "masked-test-key"
        assert "account_id" not in query
        signature = query.pop("signature")[0]
        canonical = BingXSigner.canonical_query({key: values[0] for key, values in query.items()})
        assert signature == BingXSigner.sign("test-secret", canonical)
        return response(
            request,
            {"balance": {"asset": "USDT", "balance": "1000.25", "availableMargin": "900.10"}},
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient(
        "https://open-api.bingx.com",
        "masked-test-key",
        "test-secret",
        http=http,
        clock_ms=lambda: 1_700_000_000_000,
    )
    balances = await client.balances("internal-account-id")
    assert balances[0].total == Decimal("1000.25")
    assert balances[0].available == Decimal("900.10")
    await http.aclose()


@pytest.mark.asyncio
async def test_live_order_fails_closed_until_every_gate_passes() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return response(request, {})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "masked-test-key", "test-secret", http=http)
    order = OrderRequest(
        account_id="internal",
        symbol="BTC-USDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.001"),
        client_order_id="safe-idempotency-key",
    )
    with pytest.raises(BingXLiveTradingDisabled, match="missing environment gate"):
        await client.submit_order(order)
    assert not called
    await http.aclose()


@pytest.mark.asyncio
async def test_live_order_contract_and_status_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        preflight = preflight_response(request)
        if preflight is not None:
            return preflight
        query = parse_qs(request.url.query.decode())
        assert request.method == "POST"
        assert query["clientOrderID"] == ["safe-idempotency-key"]
        assert query["quantity"] == ["0.001"]
        assert query["type"] == ["MARKET"]
        return response(
            request,
            {
                "order": {
                    "orderId": 123,
                    "clientOrderID": "safe-idempotency-key",
                    "status": "FILLED",
                    "executedQty": "0.001",
                    "avgPrice": "61000.5",
                }
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient(
        "https://open-api.bingx.com",
        "masked-test-key",
        "test-secret",
        live_gates=all_live_gates(),
        http=http,
        clock_ms=lambda: 1_700_000_000_000,
    )
    result = await client.submit_order(
        OrderRequest(
            account_id="internal",
            symbol="BTC-USDT",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.001"),
            client_order_id="safe-idempotency-key",
        )
    )
    assert result.status == OrderStatus.FILLED
    assert result.average_price == Decimal("61000.5")
    await http.aclose()


@pytest.mark.asyncio
async def test_protective_order_requires_trigger_and_is_reduce_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        preflight = preflight_response(request)
        if preflight is not None:
            return preflight
        query = parse_qs(request.url.query.decode())
        assert query["type"] == ["STOP_MARKET"]
        assert query["stopPrice"] == ["59000"]
        assert query["reduceOnly"] == ["true"]
        return response(request, {"order": {"orderId": 124, "status": "NEW"}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient(
        "https://open-api.bingx.com",
        "masked-test-key",
        "test-secret",
        live_gates=all_live_gates(),
        http=http,
    )
    request = OrderRequest(
        account_id="internal",
        symbol="BTC-USDT",
        side=Side.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=Decimal("0.001"),
        client_order_id="protective-order-id",
        trigger_price=Decimal("59000"),
        reduce_only=True,
    )
    result = await client.submit_order(request)
    assert result.status == OrderStatus.SUBMITTED
    await http.aclose()


@pytest.mark.asyncio
async def test_exchange_errors_are_normalized_without_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"code": 100001, "msg": "invalid request", "data": {}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXClient("https://open-api.bingx.com", "masked-test-key", "test-secret", http=http)
    with pytest.raises(BingXError) as captured:
        await client.price("BTC-USDT")
    assert captured.value.code == "100001"
    assert "test-secret" not in str(captured.value)
    assert "masked-test-key" not in str(captured.value)
    await http.aclose()
