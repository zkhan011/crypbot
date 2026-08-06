"""BingX perpetual-futures REST adapter.

Exchange details are deliberately confined to this module. The adapter implements
the REST operations required by the trading engine and fails closed unless every
live-execution gate supplied by the composition root is true. It never logs request
headers, signatures, or response bodies because those can contain account data.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from app.domain.trading_types import OrderStatus, OrderType, Side
from app.exchanges.interfaces import (
    Balance,
    Candle,
    OrderBook,
    OrderBookLevel,
    OrderRequest,
    OrderResult,
    Position,
    SymbolMetadata,
)
from app.exchanges.safety import OrderValidationService

QueryValue = str | int | bool | None


class BingXError(RuntimeError):
    """Normalized exchange failure without secret-bearing request details."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(f"BingX request failed ({code}): {message}")
        self.code = code
        self.retryable = retryable


class BingXLiveTradingDisabled(BingXError):
    def __init__(self, reason: str) -> None:
        super().__init__("LIVE_TRADING_BLOCKED", reason)


class BingXAuthenticationError(BingXError):
    pass


class BingXPermissionError(BingXError):
    pass


class BingXRateLimitError(BingXError):
    pass


class BingXMalformedResponseError(BingXError):
    pass


@dataclass(frozen=True)
class BingXLiveGates:
    environment_enabled: bool = False
    credential_verified: bool = False
    strategy_approved: bool = False
    risk_configured: bool = False
    final_confirmation: bool = False

    def require_all(self) -> None:
        missing = [
            name
            for name, enabled in (
                ("environment gate", self.environment_enabled),
                ("verified credential", self.credential_verified),
                ("approved strategy", self.strategy_approved),
                ("configured risk limits", self.risk_configured),
                ("final administrator confirmation", self.final_confirmation),
            )
            if not enabled
        ]
        if missing:
            raise BingXLiveTradingDisabled("missing " + ", ".join(missing))


class BingXSigner:
    @staticmethod
    def canonical_query(params: Mapping[str, object]) -> str:
        return urlencode(sorted((key, str(value)) for key, value in params.items() if value is not None))

    @staticmethod
    def sign(secret: str, canonical_query: str) -> str:
        return hmac.new(secret.encode(), canonical_query.encode(), hashlib.sha256).hexdigest()


class BingXClient:
    """Bot-required BingX perpetual-futures REST operations.

    ``account_id`` is an internal routing identifier and is never transmitted to
    BingX. A client instance represents one encrypted/verified exchange credential.
    """

    CONTRACTS_PATH = "/openApi/swap/v2/quote/contracts"
    PRICE_PATH = "/openApi/swap/v2/quote/price"
    CANDLES_PATH = "/openApi/swap/v3/quote/klines"
    DEPTH_PATH = "/openApi/swap/v2/quote/depth"
    BALANCE_PATH = "/openApi/swap/v3/user/balance"
    POSITIONS_PATH = "/openApi/swap/v2/user/positions"
    ORDER_PATH = "/openApi/swap/v2/trade/order"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_secret: str,
        *,
        live_gates: BingXLiveGates | None = None,
        timeout_seconds: Decimal = Decimal("10"),
        max_retries: int = 2,
        recv_window_ms: int = 5_000,
        http: httpx.AsyncClient | None = None,
        clock_ms: Callable[[], int] | None = None,
        order_validator: OrderValidationService | None = None,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("BingX base URL must use HTTPS")
        if not api_key or not api_secret:
            raise ValueError("BingX API credentials are required")
        if max_retries < 0 or max_retries > 5:
            raise ValueError("max_retries must be between 0 and 5")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self.live_gates = live_gates or BingXLiveGates()
        self.max_retries = max_retries
        self.recv_window_ms = recv_window_ms
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self.http = http or httpx.AsyncClient(timeout=float(timeout_seconds))
        self._owns_http = http is None
        self.order_validator = order_validator or OrderValidationService()

    async def __aenter__(self) -> BingXClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http:
            await self.http.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        params: Mapping[str, QueryValue] | None = None,
        *,
        signed: bool,
        retry_safe: bool = True,
    ) -> Any:
        request_params: dict[str, QueryValue] = dict(params or {})
        headers: dict[str, str] = {}
        if signed:
            request_params.update(timestamp=self._clock_ms(), recvWindow=self.recv_window_ms)
            signature = BingXSigner.sign(self._api_secret, BingXSigner.canonical_query(request_params))
            request_params["signature"] = signature
            headers["X-BX-APIKEY"] = self._api_key

        attempts = self.max_retries + 1 if retry_safe else 1
        for attempt in range(attempts):
            try:
                response = await self.http.request(method, f"{self.base_url}{path}", params=request_params, headers=headers)
                if response.status_code == 401:
                    raise BingXAuthenticationError("HTTP_401", "authentication failed")
                if response.status_code == 403:
                    raise BingXPermissionError("HTTP_403", "operation is not permitted")
                if response.status_code == 429:
                    raise BingXRateLimitError("HTTP_429", "rate limit exceeded", retryable=True)
                if response.status_code >= 500:
                    raise BingXError(str(response.status_code), "temporary exchange or rate-limit failure", retryable=True)
                if response.status_code >= 400:
                    raise BingXError(f"HTTP_{response.status_code}", "exchange rejected request")
                try:
                    payload = response.json()
                except ValueError:
                    raise BingXMalformedResponseError("MALFORMED_RESPONSE", "exchange returned invalid JSON") from None
                if not isinstance(payload, dict):
                    raise BingXMalformedResponseError("MALFORMED_RESPONSE", "exchange response envelope is not an object")
                code = str(payload.get("code", "0")) if isinstance(payload, dict) else "0"
                if code != "0":
                    raise BingXError(code, "exchange rejected request")
                if "data" not in payload:
                    raise BingXMalformedResponseError("MALFORMED_RESPONSE", "exchange response has no data field")
                return payload["data"]
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                error = BingXError("NETWORK", "exchange unavailable", retryable=True)
                if attempt + 1 >= attempts:
                    raise error from exc
            except BingXError as exc:
                if not exc.retryable or attempt + 1 >= attempts:
                    raise
            await asyncio.sleep(0.1 * (2**attempt))
        raise AssertionError("unreachable")

    async def symbol_metadata(self, symbol: str) -> SymbolMetadata:
        data = await self._request("GET", self.CONTRACTS_PATH, signed=False)
        for item in data or []:
            if item.get("symbol") == symbol:
                quantity_precision = int(item["quantityPrecision"])
                price_precision = int(item["pricePrecision"])
                return SymbolMetadata(
                    symbol=symbol,
                    min_quantity=Decimal(str(item.get("minQty", "0"))),
                    quantity_step=Decimal(1).scaleb(-quantity_precision),
                    tick_size=Decimal(1).scaleb(-price_precision),
                    min_notional=Decimal(str(item.get("tradeMinUSDT", item.get("minNotional", "0")))),
                )
        raise BingXError("SYMBOL_NOT_FOUND", "requested contract is unavailable")

    async def price(self, symbol: str) -> Decimal:
        data = await self._request("GET", self.PRICE_PATH, {"symbol": symbol}, signed=False)
        item = data[0] if isinstance(data, list) else data
        return Decimal(str(item["price"]))

    async def candles(self, symbol: str, interval: str, limit: int = 100) -> list[Candle]:
        if limit < 1 or limit > 1_440:
            raise ValueError("candle limit must be between 1 and 1440")
        data = await self._request("GET", self.CANDLES_PATH, {"symbol": symbol, "interval": interval, "limit": limit}, signed=False)
        return [
            Candle(
                open_time=int(item[0]),
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                volume=Decimal(str(item[5])),
            )
            for item in data or []
        ]

    async def order_book(self, symbol: str, limit: int = 20) -> OrderBook:
        if limit not in {5, 10, 20, 50, 100, 500, 1_000}:
            raise ValueError("unsupported BingX order-book depth")
        data = await self._request("GET", self.DEPTH_PATH, {"symbol": symbol, "limit": limit}, signed=False)
        return OrderBook(
            symbol=symbol,
            bids=[OrderBookLevel(price=Decimal(str(level[0])), quantity=Decimal(str(level[1]))) for level in data["bids"]],
            asks=[OrderBookLevel(price=Decimal(str(level[0])), quantity=Decimal(str(level[1]))) for level in data["asks"]],
            exchange_timestamp=int(data["T"]) if data.get("T") is not None else None,
        )

    async def balances(self, account_id: str) -> list[Balance]:
        data = await self._request("GET", self.BALANCE_PATH, signed=True)
        values = data.get("balance", data) if isinstance(data, dict) else data
        if isinstance(values, dict):
            values = [values]
        return [
            Balance(
                asset=str(item.get("asset", "USDT")),
                total=Decimal(str(item.get("balance", item.get("equity", "0")))),
                available=Decimal(str(item.get("availableMargin", item.get("availableBalance", "0")))),
            )
            for item in values or []
        ]

    async def positions(self, account_id: str) -> list[Position]:
        data = await self._request("GET", self.POSITIONS_PATH, signed=True)
        positions: list[Position] = []
        for item in data or []:
            quantity = Decimal(str(item.get("positionAmt", "0")))
            if quantity == 0:
                continue
            position_side = str(item.get("positionSide", "")).upper()
            side = Side.BUY if position_side == "LONG" or quantity > 0 else Side.SELL
            positions.append(
                Position(
                    symbol=str(item["symbol"]),
                    side=side,
                    quantity=abs(quantity),
                    entry_price=Decimal(str(item.get("avgPrice", "0"))),
                    leverage=Decimal(str(item.get("leverage", "1"))),
                )
            )
        return positions

    async def submit_order(self, request: OrderRequest) -> OrderResult:
        self.live_gates.require_all()
        rules = await self.symbol_metadata(request.symbol)
        reference_price = request.price or await self.price(request.symbol)
        request, _validation = self.order_validator.validate_and_normalize(request, rules, reference_price=reference_price)
        order_type = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT",
            OrderType.STOP_LOSS: "STOP_MARKET",
            OrderType.TAKE_PROFIT: "TAKE_PROFIT_MARKET",
        }.get(request.order_type)
        if order_type is None:
            raise BingXError("UNSUPPORTED_ORDER_TYPE", "order type is not supported")
        if request.order_type == OrderType.LIMIT and request.price is None:
            raise ValueError("limit order requires price")
        if request.order_type in {OrderType.STOP_LOSS, OrderType.TAKE_PROFIT} and request.trigger_price is None:
            raise ValueError("protective order requires trigger_price")
        params: dict[str, QueryValue] = {
            "symbol": request.symbol,
            "side": request.side.value,
            "type": order_type,
            "quantity": str(request.quantity),
            "clientOrderID": request.client_order_id,
        }
        if request.price is not None:
            params["price"] = str(request.price)
        if request.trigger_price is not None:
            params["stopPrice"] = str(request.trigger_price)
        if request.reduce_only:
            params["reduceOnly"] = "true"
        data = await self._request("POST", self.ORDER_PATH, params, signed=True, retry_safe=False)
        return self._parse_order(data, request.client_order_id)

    async def get_order_by_client_id(self, account_id: str, client_order_id: str) -> OrderResult | None:
        try:
            data = await self._request("GET", self.ORDER_PATH, {"clientOrderID": client_order_id}, signed=True)
        except BingXError as exc:
            if exc.code in {"80014", "ORDER_NOT_FOUND"}:
                return None
            raise
        return self._parse_order(data, client_order_id)

    async def cancel_order(self, account_id: str, client_order_id: str) -> OrderResult:
        self.live_gates.require_all()
        data = await self._request("DELETE", self.ORDER_PATH, {"clientOrderID": client_order_id}, signed=True, retry_safe=False)
        return self._parse_order(data, client_order_id, fallback_status=OrderStatus.CANCELLED)

    @staticmethod
    def _parse_order(data: Any, client_order_id: str, fallback_status: OrderStatus = OrderStatus.SUBMITTED) -> OrderResult:
        item = data.get("order", data) if isinstance(data, dict) else {}
        status_map = {
            "NEW": OrderStatus.SUBMITTED,
            "PENDING": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
        }
        return OrderResult(
            client_order_id=str(item.get("clientOrderID", item.get("clientOrderId", client_order_id))),
            exchange_order_id=str(item["orderId"]) if item.get("orderId") is not None else None,
            status=status_map.get(str(item.get("status", "")).upper(), fallback_status),
            filled_quantity=Decimal(str(item.get("executedQty", item.get("cumQty", "0")))),
            average_price=(Decimal(str(item.get("avgPrice"))) if item.get("avgPrice") not in {None, "", "0"} else None),
        )
