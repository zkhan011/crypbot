from decimal import Decimal

import httpx
import pytest

from app.exchanges.bingx_market import BingXMarketDataError, BingXPublicMarketClient
from app.main import bingx_readiness


@pytest.mark.asyncio
async def test_public_prices_are_decimal_and_require_success_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openApi/swap/v2/quote/price"
        assert "X-BX-APIKEY" not in request.headers
        return httpx.Response(
            200,
            request=request,
            json={
                "code": 0,
                "msg": "",
                "data": [
                    {"symbol": "ETH-USDT", "price": "3500.125"},
                    {"symbol": "BTC-USDT", "price": "65000.50"},
                ],
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXPublicMarketClient("https://open-api.bingx.com", http=http)
    prices = await client.prices(("BTC-USDT", "ETH-USDT"))
    assert [(price.symbol, price.price) for price in prices] == [
        ("BTC-USDT", Decimal("65000.50")),
        ("ETH-USDT", Decimal("3500.125")),
    ]
    assert client.last_success_at is not None
    await http.aclose()


@pytest.mark.asyncio
async def test_public_prices_fail_closed_on_exchange_code_or_missing_symbol() -> None:
    responses = iter(
        [
            {"code": 100001, "msg": "rejected", "data": {}},
            {"code": 0, "msg": "", "data": [{"symbol": "BTC-USDT", "price": "65000"}]},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=next(responses))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = BingXPublicMarketClient("https://open-api.bingx.com", http=http)
    with pytest.raises(BingXMarketDataError, match="rejected"):
        await client.prices(("BTC-USDT",))
    with pytest.raises(BingXMarketDataError, match="omitted"):
        await client.prices(("BTC-USDT", "ETH-USDT"))
    assert client.last_error_at is not None
    await http.aclose()


def test_public_market_client_rejects_non_allowlisted_url() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        BingXPublicMarketClient("https://example.invalid")


def test_readiness_explains_live_gates_without_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BINGX_API_KEY", "sensitive-key-value")
    monkeypatch.setenv("BINGX_API_SECRET", "sensitive-secret-value")
    readiness = bingx_readiness()
    assert readiness["opening_orders_allowed"] is False
    assert readiness["adapter_runtime_connected"] is False
    assert readiness["live_gate_status"]["credentials_complete"] is True
    rendered = str(readiness)
    assert "sensitive-key-value" not in rendered
    assert "sensitive-secret-value" not in rendered
