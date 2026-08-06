"""Fail-closed BingX USDT-M perpetual REST integration.

Only contracts supplied in the task specification are implemented. Exchange code
stays in this module; strategy and HTTP layers never receive credential material.
LIVE mutations require explicit gates and remain disabled by default.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, TypeVar
from urllib.parse import urlencode
from uuid import uuid4

import httpx

from app.domain.trading_types import MarginType, OrderStatus, OrderType, PositionSide, Side
from app.exchanges.interfaces import (
    Balance,
    Candle,
    CommissionRate,
    Fill,
    FundingRate,
    IncomeRecord,
    OrderBook,
    OrderBookLevel,
    OrderRequest,
    OrderResult,
    Position,
    PremiumIndex,
    SymbolMetadata,
    Ticker24h,
    Trade,
)
from app.exchanges.resilience import BingXTimeSynchronizer, CircuitBreaker, EndpointRateLimiter, RateLimit, RateLimitScope
from app.exchanges.safety import OrderValidationService, TradingRulesCache

QueryValue = str | int | bool | None
T = TypeVar("T")


class BingXError(RuntimeError):
    """Normalized failure that never includes request/response secret material."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(f"BingX request failed ({code}): {message}")
        self.code = code
        self.retryable = retryable


class BingXAuthenticationError(BingXError):
    pass


class BingXInvalidSignatureError(BingXAuthenticationError):
    pass


class BingXTimestampError(BingXError):
    pass


class BingXInvalidParameterError(BingXError):
    pass


class BingXUnsupportedSymbolError(BingXError):
    pass


class BingXInsufficientBalanceError(BingXError):
    pass


class BingXInsufficientMarginError(BingXError):
    pass


class BingXInvalidLeverageError(BingXError):
    pass


class BingXPositionLimitError(BingXError):
    pass


class BingXOrderRejectedError(BingXError):
    pass


class BingXOrderNotFoundError(BingXError):
    pass


class BingXRateLimitError(BingXError):
    pass


class BingXRiskRestrictionError(BingXError):
    pass


class BingXNetworkTimeoutError(BingXError, TimeoutError):
    pass


class BingXMalformedResponseError(BingXError):
    pass


class BingXExchangeFailureError(BingXError):
    pass


class BingXPermissionError(BingXError):
    pass


class BingXLiveTradingDisabled(BingXError):
    def __init__(self, reason: str) -> None:
        super().__init__("LIVE_TRADING_BLOCKED", reason)


class UnsupportedCopyTradingOperation(BingXError):
    def __init__(self, operation: str) -> None:
        super().__init__("COPY_TRADING_SCHEMA_UNAVAILABLE", f"{operation} is disabled until its request schema is configured")


ERROR_TYPES: dict[str, type[BingXError]] = {
    "101206": BingXInsufficientBalanceError,
    "101209": BingXPositionLimitError,
    "101211": BingXInvalidParameterError,
    "101414": BingXInvalidLeverageError,
    "101415": BingXUnsupportedSymbolError,
    "101419": BingXOrderRejectedError,
    "109403": BingXRiskRestrictionError,
    "109417": BingXUnsupportedSymbolError,
    "109420": BingXOrderNotFoundError,
    "109421": BingXOrderNotFoundError,
    "109425": BingXUnsupportedSymbolError,
    "109429": BingXRateLimitError,
    "110287": BingXPositionLimitError,
    "110400": BingXInvalidParameterError,
    "110402": BingXInvalidParameterError,
    "110406": BingXOrderRejectedError,
}


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

    def require_reduction(self) -> None:
        if not self.environment_enabled or not self.credential_verified or not self.final_confirmation:
            raise BingXLiveTradingDisabled("risk-reducing operation requires environment, credential, and confirmation gates")


class BingXSigner:
    @staticmethod
    def canonical_query(params: Mapping[str, object]) -> str:
        return urlencode(sorted((key, str(value)) for key, value in params.items() if value is not None))

    @staticmethod
    def sign(secret: str, canonical_query: str) -> str:
        return hmac.new(secret.encode(), canonical_query.encode(), hashlib.sha256).hexdigest()


class BingXClient:
    SERVER_TIME_PATH = "/openApi/swap/v2/server/time"
    CONTRACTS_PATH = "/openApi/swap/v2/quote/contracts"
    TRADING_RULES_PATH = "/openApi/swap/v1/tradingRules"
    PRICE_PATH = "/openApi/swap/v2/quote/price"
    DEPTH_PATH = "/openApi/swap/v2/quote/depth"
    TRADES_PATH = "/openApi/swap/v2/quote/trades"
    HISTORICAL_TRADES_PATH = "/openApi/swap/v1/market/historicalTrades"
    CANDLES_PATH = "/openApi/swap/v3/quote/klines"
    MARK_CANDLES_PATH = "/openApi/swap/v1/market/markPriceKlines"
    PREMIUM_INDEX_PATH = "/openApi/swap/v2/quote/premiumIndex"
    FUNDING_RATE_PATH = "/openApi/swap/v2/quote/fundingRate"
    OPEN_INTEREST_PATH = "/openApi/swap/v2/quote/openInterest"
    TICKER_PATH = "/openApi/swap/v2/quote/ticker"
    TICKER_PRICE_PATH = "/openApi/swap/v1/ticker/price"
    BOOK_TICKER_PATH = "/openApi/swap/v2/quote/bookTicker"
    BALANCE_PATH = "/openApi/swap/v2/user/balance"
    POSITIONS_PATH = "/openApi/swap/v2/user/positions"
    INCOME_PATH = "/openApi/swap/v2/user/income"
    INCOME_EXPORT_PATH = "/openApi/swap/v2/user/income/export"
    COMMISSION_PATH = "/openApi/swap/v2/user/commissionRate"
    POSITION_MODE_PATH = "/openApi/swap/v1/positionSide/dual"
    MARGIN_TYPE_PATH = "/openApi/swap/v2/trade/marginType"
    LEVERAGE_PATH = "/openApi/swap/v2/trade/leverage"
    ORDER_TEST_PATH = "/openApi/swap/v2/trade/order/test"
    ORDER_PATH = "/openApi/swap/v2/trade/order"
    BATCH_ORDERS_PATH = "/openApi/swap/v2/trade/batchOrders"
    OPEN_ORDERS_PATH = "/openApi/swap/v2/trade/openOrders"
    ALL_ORDERS_PATH = "/openApi/swap/v2/trade/allOrders"
    FILLS_PATH = "/openApi/swap/v2/trade/allFillOrders"
    CANCEL_ALL_PATH = "/openApi/swap/v2/trade/allOpenOrders"
    CLOSE_ALL_PATH = "/openApi/swap/v2/trade/closeAllPositions"
    CLOSE_POSITION_PATH = "/openApi/swap/v1/trade/closePosition"
    CANCEL_REPLACE_PATH = "/openApi/swap/v1/trade/cancelReplace"
    BATCH_CANCEL_REPLACE_PATH = "/openApi/swap/v1/trade/batchCancelReplace"
    CANCEL_ALL_AFTER_PATH = "/openApi/swap/v2/trade/cancelAllAfter"
    POSITION_MARGIN_PATH = "/openApi/swap/v2/trade/positionMargin"
    FORCE_ORDERS_PATH = "/openApi/swap/v2/trade/forceOrders"

    VALID_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}

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
        time_synchronizer: BingXTimeSynchronizer | None = None,
        rate_limiter: EndpointRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        allow_test_orders: bool = False,
        rule_cache_seconds: Decimal = Decimal("900"),
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
        wall_clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self.time_synchronizer = time_synchronizer or BingXTimeSynchronizer(wall_clock_ms=wall_clock)
        self.http = http or httpx.AsyncClient(
            timeout=float(timeout_seconds), limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
        self._owns_http = http is None
        self.order_validator = order_validator or OrderValidationService()
        self.rate_limiter = rate_limiter or EndpointRateLimiter(
            {
                RateLimitScope.MARKET_DATA: RateLimit(20, Decimal("1")),
                RateLimitScope.ACCOUNT: RateLimit(5, Decimal("1")),
                RateLimitScope.ORDER_CREATE: RateLimit(2, Decimal("1")),
                RateLimitScope.ORDER_CANCEL: RateLimit(5, Decimal("1")),
                RateLimitScope.POSITION_CONTROL: RateLimit(2, Decimal("1")),
            }
        )
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.allow_test_orders = allow_test_orders
        self.rule_cache = TradingRulesCache(rule_cache_seconds)

    async def __aenter__(self) -> BingXClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http:
            await self.http.aclose()

    @staticmethod
    def _decimal(value: object, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise BingXMalformedResponseError("MALFORMED_RESPONSE", f"invalid decimal field: {field}") from exc
        if not result.is_finite():
            raise BingXMalformedResponseError("MALFORMED_RESPONSE", f"non-finite decimal field: {field}")
        return result

    @staticmethod
    def _integer(value: object, field: str) -> int:
        try:
            return int(str(value))
        except ValueError as exc:
            raise BingXMalformedResponseError("MALFORMED_RESPONSE", f"invalid integer field: {field}") from exc

    @staticmethod
    def _items(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            return data
        if isinstance(data, dict):
            return [data]
        raise BingXMalformedResponseError("MALFORMED_RESPONSE", "expected object or object list")

    @staticmethod
    def _error(code: str, message: object) -> BingXError:
        normalized_message = str(message or "").lower()
        if "timestamp" in normalized_message or "recvwindow" in normalized_message:
            return BingXTimestampError(code, "request timestamp rejected")
        if "signature" in normalized_message:
            return BingXInvalidSignatureError(code, "request signature rejected")
        error_type = ERROR_TYPES.get(code, BingXExchangeFailureError)
        retryable = error_type is BingXRateLimitError
        return error_type(code, "exchange rejected request", retryable=retryable)

    async def _request(
        self,
        method: str,
        path: str,
        params: Mapping[str, QueryValue] | None = None,
        *,
        signed: bool,
        scope: RateLimitScope,
        retry_safe: bool = True,
        timestamped: bool = True,
        risk_reducing: bool = False,
        allow_clock_retry: bool = True,
    ) -> Any:
        await self.circuit_breaker.require_available(risk_reducing=risk_reducing)
        await self.rate_limiter.acquire(scope, risk_reducing=risk_reducing)
        base_params: dict[str, QueryValue] = dict(params or {})
        attempts = (self.max_retries + 1 if retry_safe else 1) + (1 if signed and allow_clock_retry else 0)
        clock_retried = False
        for attempt in range(attempts):
            request_params = dict(base_params)
            if timestamped:
                request_params["timestamp"] = self.time_synchronizer.now_ms()
            headers = {"X-Request-ID": str(uuid4())}
            if signed:
                request_params["recvWindow"] = self.recv_window_ms
                request_params["signature"] = BingXSigner.sign(self._api_secret, BingXSigner.canonical_query(request_params))
                headers["X-BX-APIKEY"] = self._api_key
            try:
                response = await self.http.request(method, f"{self.base_url}{path}", params=request_params, headers=headers)
                if response.status_code == 401:
                    raise BingXAuthenticationError("HTTP_401", "authentication failed")
                if response.status_code == 403:
                    raise BingXPermissionError("HTTP_403", "operation is not permitted")
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_safe:
                        await asyncio.sleep(min(float(retry_after), 5.0))
                    raise BingXRateLimitError("HTTP_429", "rate limit exceeded", retryable=True)
                if response.status_code >= 500:
                    raise BingXExchangeFailureError(f"HTTP_{response.status_code}", "exchange unavailable", retryable=True)
                if response.status_code >= 400:
                    raise BingXExchangeFailureError(f"HTTP_{response.status_code}", "exchange rejected request")
                try:
                    payload = response.json()
                except ValueError:
                    raise BingXMalformedResponseError("MALFORMED_RESPONSE", "exchange returned invalid JSON") from None
                if not isinstance(payload, dict) or "code" not in payload or "data" not in payload:
                    raise BingXMalformedResponseError("MALFORMED_RESPONSE", "invalid BingX response envelope")
                code = str(payload["code"])
                if code != "0":
                    error = self._error(code, payload.get("msg"))
                    if isinstance(error, BingXTimestampError) and signed and allow_clock_retry and not clock_retried:
                        await self.synchronize_time(force=True)
                        clock_retried = True
                        continue
                    raise error
                await self.circuit_breaker.record_success()
                return payload["data"]
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                await self.circuit_breaker.record_failure()
                if attempt + 1 >= attempts:
                    raise BingXNetworkTimeoutError("NETWORK_TIMEOUT", "exchange request timed out", retryable=True) from exc
            except BingXError as exc:
                if not exc.retryable or attempt + 1 >= attempts:
                    raise
            await asyncio.sleep(min(0.1 * (2**attempt), 2.0))
        raise AssertionError("unreachable")

    async def server_time(self) -> int:
        data = await self._request("GET", self.SERVER_TIME_PATH, signed=False, scope=RateLimitScope.MARKET_DATA, timestamped=False)
        if isinstance(data, int):
            return data
        if isinstance(data, dict):
            for field in ("serverTime", "time", "timestamp"):
                value = data.get(field)
                if value is not None:
                    return int(value)
        raise BingXMalformedResponseError("MALFORMED_RESPONSE", "server time field is missing")

    async def synchronize_time(self, *, force: bool = False) -> int:
        return await self.time_synchronizer.synchronize(self.server_time, force=force)

    async def contracts(self, symbol: str | None = None) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", self.CONTRACTS_PATH, {"symbol": symbol}, signed=False, scope=RateLimitScope.MARKET_DATA, timestamped=False
        )
        return self._items(data)

    async def symbol_metadata(self, symbol: str) -> SymbolMetadata:
        return await self.rule_cache.get(symbol, self._load_symbol_metadata)

    async def _load_symbol_metadata(self, symbol: str) -> SymbolMetadata:
        for item in await self.contracts(symbol):
            if item.get("symbol") == symbol:
                quantity_precision = int(item.get("quantityPrecision", 0))
                price_precision = int(item.get("pricePrecision", 0))
                status = str(item.get("status", item.get("state", "TRADING"))).upper()
                return SymbolMetadata(
                    symbol=symbol,
                    min_quantity=self._decimal(item.get("minQty", "0"), "minQty"),
                    max_quantity=(self._decimal(item["maxQty"], "maxQty") if item.get("maxQty") is not None else None),
                    quantity_step=Decimal(1).scaleb(-quantity_precision),
                    tick_size=Decimal(1).scaleb(-price_precision),
                    min_notional=self._decimal(item.get("tradeMinUSDT", item.get("minNotional", "0")), "minNotional"),
                    active=status in {"TRADING", "ONLINE", "1", "TRUE"},
                )
        raise BingXUnsupportedSymbolError("SYMBOL_NOT_FOUND", "requested contract is unavailable")

    async def trading_rules(self, symbol: str) -> list[dict[str, Any]]:
        data = await self._request("GET", self.TRADING_RULES_PATH, {"symbol": symbol}, signed=True, scope=RateLimitScope.ACCOUNT)
        return self._items(data)

    async def prices(self, symbol: str | None = None) -> list[tuple[str, Decimal]]:
        data = await self._request("GET", self.PRICE_PATH, {"symbol": symbol}, signed=False, scope=RateLimitScope.MARKET_DATA)
        return [(str(item.get("symbol", symbol or "")), self._decimal(item["price"], "price")) for item in self._items(data)]

    async def price(self, symbol: str) -> Decimal:
        values = await self.prices(symbol)
        if not values:
            raise BingXUnsupportedSymbolError("SYMBOL_NOT_FOUND", "price unavailable")
        return values[0][1]

    @classmethod
    def _validate_interval(cls, interval: str) -> None:
        if interval not in cls.VALID_INTERVALS:
            raise BingXInvalidParameterError("INVALID_INTERVAL", "unsupported candle interval")

    async def candles(
        self, symbol: str, interval: str, limit: int = 100, start_time: int | None = None, end_time: int | None = None
    ) -> list[Candle]:
        self._validate_interval(interval)
        if limit < 1 or limit > 1_440:
            raise BingXInvalidParameterError("INVALID_LIMIT", "candle limit must be between 1 and 1440")
        data = await self._request(
            "GET",
            self.CANDLES_PATH,
            {"symbol": symbol, "interval": interval, "startTime": start_time, "endTime": end_time, "limit": limit},
            signed=False,
            scope=RateLimitScope.MARKET_DATA,
        )
        return self._parse_candles(data)

    async def mark_price_candles(
        self, symbol: str, interval: str, limit: int = 100, start_time: int | None = None, end_time: int | None = None
    ) -> list[Candle]:
        self._validate_interval(interval)
        data = await self._request(
            "GET",
            self.MARK_CANDLES_PATH,
            {"symbol": symbol, "interval": interval, "startTime": start_time, "endTime": end_time, "limit": limit},
            signed=False,
            scope=RateLimitScope.MARKET_DATA,
        )
        return self._parse_candles(data)

    def _parse_candles(self, data: Any) -> list[Candle]:
        if not isinstance(data, list):
            raise BingXMalformedResponseError("MALFORMED_RESPONSE", "candles must be a list")
        result: list[Candle] = []
        for item in data:
            if isinstance(item, list) and len(item) >= 6:
                result.append(
                    Candle(
                        open_time=int(item[0]),
                        open=self._decimal(item[1], "open"),
                        high=self._decimal(item[2], "high"),
                        low=self._decimal(item[3], "low"),
                        close=self._decimal(item[4], "close"),
                        volume=self._decimal(item[5], "volume"),
                    )
                )
            elif isinstance(item, dict):
                result.append(
                    Candle(
                        open_time=self._integer(item.get("time", item.get("openTime", 0)), "openTime"),
                        open=self._decimal(item["open"], "open"),
                        high=self._decimal(item["high"], "high"),
                        low=self._decimal(item["low"], "low"),
                        close=self._decimal(item["close"], "close"),
                        volume=self._decimal(item["volume"], "volume"),
                    )
                )
            else:
                raise BingXMalformedResponseError("MALFORMED_RESPONSE", "invalid candle item")
        return result

    async def order_book(self, symbol: str, limit: int = 20) -> OrderBook:
        data = await self._request(
            "GET", self.DEPTH_PATH, {"symbol": symbol, "limit": limit}, signed=False, scope=RateLimitScope.MARKET_DATA
        )
        if not isinstance(data, dict):
            raise BingXMalformedResponseError("MALFORMED_RESPONSE", "order book must be an object")
        return OrderBook(
            symbol=symbol,
            bids=[
                OrderBookLevel(price=self._decimal(level[0], "bid price"), quantity=self._decimal(level[1], "bid quantity"))
                for level in data.get("bids", [])
            ],
            asks=[
                OrderBookLevel(price=self._decimal(level[0], "ask price"), quantity=self._decimal(level[1], "ask quantity"))
                for level in data.get("asks", [])
            ],
            exchange_timestamp=self._integer(data.get("T", data.get("timestamp", 0)), "timestamp") or None,
        )

    async def recent_trades(self, symbol: str, limit: int | None = None) -> list[Trade]:
        data = await self._request(
            "GET", self.TRADES_PATH, {"symbol": symbol, "limit": limit}, signed=False, scope=RateLimitScope.MARKET_DATA
        )
        return self._parse_trades(data, symbol)

    async def historical_trades(self, symbol: str, limit: int | None = None, from_id: str | None = None) -> list[Trade]:
        data = await self._request(
            "GET",
            self.HISTORICAL_TRADES_PATH,
            {"symbol": symbol, "limit": limit, "fromId": from_id},
            signed=False,
            scope=RateLimitScope.MARKET_DATA,
        )
        return self._parse_trades(data, symbol)

    def _parse_trades(self, data: Any, symbol: str) -> list[Trade]:
        return [
            Trade(
                trade_id=str(item.get("id", item.get("tradeId", ""))),
                symbol=str(item.get("symbol", symbol)),
                price=self._decimal(item.get("price", "0"), "trade price"),
                quantity=self._decimal(item.get("qty", item.get("quantity", "0")), "trade quantity"),
                side=(Side.SELL if item.get("isBuyerMaker") else Side.BUY) if "isBuyerMaker" in item else None,
                timestamp=int(item.get("time", item.get("timestamp", 0))) or None,
            )
            for item in self._items(data)
        ]

    async def premium_index(self, symbol: str | None = None) -> list[PremiumIndex]:
        data = await self._request("GET", self.PREMIUM_INDEX_PATH, {"symbol": symbol}, signed=False, scope=RateLimitScope.MARKET_DATA)
        return [
            PremiumIndex(
                symbol=str(item.get("symbol", symbol or "")),
                mark_price=self._decimal(item.get("markPrice", "0"), "markPrice"),
                index_price=self._decimal(item.get("indexPrice", "0"), "indexPrice"),
                funding_rate=(self._decimal(item["lastFundingRate"], "fundingRate") if item.get("lastFundingRate") is not None else None),
                next_funding_time=int(item.get("nextFundingTime", 0)) or None,
            )
            for item in self._items(data)
        ]

    async def funding_rates(
        self, symbol: str | None = None, start_time: int | None = None, end_time: int | None = None, limit: int | None = None
    ) -> list[FundingRate]:
        data = await self._request(
            "GET",
            self.FUNDING_RATE_PATH,
            {"symbol": symbol, "startTime": start_time, "endTime": end_time, "limit": limit},
            signed=False,
            scope=RateLimitScope.MARKET_DATA,
        )
        return [
            FundingRate(
                symbol=str(i.get("symbol", symbol or "")),
                funding_rate=self._decimal(i.get("fundingRate", "0"), "fundingRate"),
                funding_time=int(i.get("fundingTime", 0)),
            )
            for i in self._items(data)
        ]

    async def open_interest(self, symbol: str) -> Decimal:
        data = await self._request("GET", self.OPEN_INTEREST_PATH, {"symbol": symbol}, signed=False, scope=RateLimitScope.MARKET_DATA)
        item = self._items(data)[0]
        return self._decimal(item.get("openInterest", "0"), "openInterest")

    async def ticker_24h(self, symbol: str | None = None) -> list[Ticker24h]:
        data = await self._request("GET", self.TICKER_PATH, {"symbol": symbol}, signed=False, scope=RateLimitScope.MARKET_DATA)
        return [
            Ticker24h(
                symbol=str(i.get("symbol", symbol or "")),
                last_price=self._decimal(i.get("lastPrice", i.get("price", "0")), "lastPrice"),
                price_change=self._decimal(i.get("priceChange", "0"), "priceChange"),
                price_change_percent=self._decimal(i.get("priceChangePercent", "0"), "priceChangePercent"),
                volume=self._decimal(i.get("volume", "0"), "volume"),
                quote_volume=self._decimal(i.get("quoteVolume", "0"), "quoteVolume"),
            )
            for i in self._items(data)
        ]

    async def ticker_prices(self, symbol: str | None = None) -> list[tuple[str, Decimal]]:
        data = await self._request("GET", self.TICKER_PRICE_PATH, {"symbol": symbol}, signed=False, scope=RateLimitScope.MARKET_DATA)
        return [(str(i.get("symbol", symbol or "")), self._decimal(i.get("price", "0"), "price")) for i in self._items(data)]

    async def best_bid_ask(self, symbol: str) -> tuple[Decimal, Decimal]:
        data = await self._request("GET", self.BOOK_TICKER_PATH, {"symbol": symbol}, signed=False, scope=RateLimitScope.MARKET_DATA)
        item = self._items(data)[0]
        return self._decimal(item.get("bidPrice", "0"), "bidPrice"), self._decimal(item.get("askPrice", "0"), "askPrice")

    async def balances(self, account_id: str) -> list[Balance]:
        data = await self._request("GET", self.BALANCE_PATH, signed=True, scope=RateLimitScope.ACCOUNT)
        values = data.get("balance", data) if isinstance(data, dict) else data
        return [
            Balance(
                asset=str(i.get("asset", "USDT")),
                total=self._decimal(i.get("balance", i.get("equity", "0")), "balance"),
                available=self._decimal(i.get("availableMargin", i.get("availableBalance", "0")), "available"),
            )
            for i in self._items(values)
        ]

    async def positions(self, account_id: str, symbol: str | None = None) -> list[Position]:
        data = await self._request("GET", self.POSITIONS_PATH, {"symbol": symbol}, signed=True, scope=RateLimitScope.ACCOUNT)
        result: list[Position] = []
        for item in self._items(data):
            quantity = self._decimal(item.get("positionAmt", item.get("positionAmount", "0")), "position quantity")
            if quantity == 0:
                continue
            raw_position_side = str(item.get("positionSide", "BOTH")).upper()
            try:
                position_side = PositionSide(raw_position_side)
            except ValueError:
                position_side = PositionSide.BOTH
            side = Side.BUY if position_side == PositionSide.LONG or quantity > 0 else Side.SELL
            result.append(
                Position(
                    symbol=str(item["symbol"]),
                    side=side,
                    quantity=abs(quantity),
                    entry_price=self._decimal(item.get("avgPrice", "0"), "avgPrice"),
                    leverage=self._decimal(item.get("leverage", "1"), "leverage"),
                    position_id=str(item["positionId"]) if item.get("positionId") is not None else None,
                    position_side=position_side,
                    available_quantity=self._decimal(item.get("availableAmt", item.get("availableAmount", "0")), "available quantity"),
                    mark_price=self._decimal(item.get("markPrice", "0"), "markPrice"),
                    margin_type=str(item.get("marginType")) if item.get("marginType") is not None else None,
                    liquidation_price=self._decimal(item["liquidationPrice"], "liquidationPrice")
                    if item.get("liquidationPrice") not in {None, ""}
                    else None,
                    unrealized_pnl=self._decimal(item.get("unrealizedProfit", item.get("unrealizedPnl", "0")), "unrealizedPnl"),
                    realized_pnl=self._decimal(item.get("realisedProfit", item.get("realizedPnl", "0")), "realizedPnl"),
                    update_time=int(item.get("updateTime", 0)) or None,
                )
            )
        return result

    async def income_history(
        self,
        symbol: str | None = None,
        income_type: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = None,
    ) -> list[IncomeRecord]:
        data = await self._request(
            "GET",
            self.INCOME_PATH,
            {"symbol": symbol, "incomeType": income_type, "startTime": start_time, "endTime": end_time, "limit": limit},
            signed=True,
            scope=RateLimitScope.ACCOUNT,
        )
        return [
            IncomeRecord(
                symbol=str(i["symbol"]) if i.get("symbol") else None,
                income_type=str(i["incomeType"]) if i.get("incomeType") else None,
                income=self._decimal(i.get("income", "0"), "income"),
                asset=str(i["asset"]) if i.get("asset") else None,
                timestamp=int(i.get("time", i.get("timestamp", 0))) or None,
            )
            for i in self._items(data)
        ]

    async def income_export(self) -> Any:
        """Internal authenticated export; this is never exposed by a public API route."""
        return await self._request("GET", self.INCOME_EXPORT_PATH, signed=True, scope=RateLimitScope.ACCOUNT)

    async def commission_rate(self, symbol: str) -> CommissionRate:
        data = await self._request("GET", self.COMMISSION_PATH, {"symbol": symbol}, signed=True, scope=RateLimitScope.ACCOUNT)
        item = self._items(data)[0]
        return CommissionRate(
            symbol=symbol,
            maker_rate=self._decimal(item.get("makerCommissionRate", item.get("makerRate", "0")), "makerRate"),
            taker_rate=self._decimal(item.get("takerCommissionRate", item.get("takerRate", "0")), "takerRate"),
        )

    async def position_mode(self) -> bool:
        data = await self._request("GET", self.POSITION_MODE_PATH, signed=True, scope=RateLimitScope.ACCOUNT)
        item = self._items(data)[0]
        return str(item.get("dualSidePosition", "false")).lower() == "true"

    async def set_position_mode(self, hedge_mode: bool, *, has_positions: bool, has_open_orders: bool) -> None:
        self.live_gates.require_all()
        if has_positions or has_open_orders:
            raise BingXRiskRestrictionError("POSITION_MODE_CONFLICT", "cannot change position mode with positions or orders")
        await self._request(
            "POST",
            self.POSITION_MODE_PATH,
            {"dualSidePosition": str(hedge_mode).lower()},
            signed=True,
            scope=RateLimitScope.POSITION_CONTROL,
            retry_safe=False,
        )

    async def margin_mode(self, symbol: str) -> str:
        data = await self._request("GET", self.MARGIN_TYPE_PATH, {"symbol": symbol}, signed=True, scope=RateLimitScope.ACCOUNT)
        return str(self._items(data)[0].get("marginType", ""))

    async def set_margin_mode(self, symbol: str, margin_type: MarginType, *, has_position: bool, has_open_orders: bool) -> None:
        self.live_gates.require_all()
        if has_position or has_open_orders:
            raise BingXRiskRestrictionError("MARGIN_MODE_CONFLICT", "cannot change margin mode with position or orders")
        await self._request(
            "POST",
            self.MARGIN_TYPE_PATH,
            {"symbol": symbol, "marginType": margin_type.value},
            signed=True,
            scope=RateLimitScope.POSITION_CONTROL,
            retry_safe=False,
        )

    async def leverage(self, symbol: str) -> dict[str, Decimal]:
        data = await self._request("GET", self.LEVERAGE_PATH, {"symbol": symbol}, signed=True, scope=RateLimitScope.ACCOUNT)
        item = self._items(data)[0]
        return {str(k): self._decimal(v, str(k)) for k, v in item.items() if "leverage" in str(k).lower()}

    async def set_leverage(
        self, symbol: str, side: PositionSide, leverage: Decimal, *, maximum: Decimal, current: Decimal, allow_increase: bool = False
    ) -> None:
        self.live_gates.require_all()
        if leverage <= 0 or leverage > maximum or (leverage > current and not allow_increase):
            raise BingXInvalidLeverageError("INVALID_LEVERAGE", "requested leverage violates configured limits")
        await self._request(
            "POST",
            self.LEVERAGE_PATH,
            {"symbol": symbol, "side": side.value, "leverage": str(leverage)},
            signed=True,
            scope=RateLimitScope.POSITION_CONTROL,
            retry_safe=False,
        )

    def _order_params(self, request: OrderRequest) -> dict[str, QueryValue]:
        type_map = {OrderType.STOP_LOSS: "STOP_MARKET", OrderType.TAKE_PROFIT: "TAKE_PROFIT_MARKET"}
        order_type = type_map.get(request.order_type, request.order_type.value)
        params: dict[str, QueryValue] = {
            "symbol": request.symbol,
            "side": request.side.value,
            "positionSide": request.position_side.value,
            "type": order_type,
            "quantity": str(request.quantity),
            "clientOrderID": request.client_order_id,
        }
        if request.price is not None and order_type in {"LIMIT", "STOP", "TAKE_PROFIT", "TRIGGER_LIMIT"}:
            params["price"] = str(request.price)
        if request.trigger_price is not None and order_type not in {"MARKET", "LIMIT"}:
            params["stopPrice"] = str(request.trigger_price)
        if request.time_in_force is not None and order_type != "MARKET":
            params["timeInForce"] = request.time_in_force.value
        if request.reduce_only:
            params["reduceOnly"] = "true"
        if request.working_type is not None:
            params["workingType"] = request.working_type
        if request.price_protect is not None:
            params["priceProtect"] = str(request.price_protect).lower()
        if request.close_position:
            params["closePosition"] = "true"
            params.pop("quantity", None)
        return params

    async def _validated_order(self, request: OrderRequest) -> OrderRequest:
        rules = await self.symbol_metadata(request.symbol)
        reference_price = request.price or await self.price(request.symbol)
        normalized, _ = self.order_validator.validate_and_normalize(request, rules, reference_price=reference_price)
        return normalized

    async def test_order(self, request: OrderRequest) -> None:
        if not self.allow_test_orders:
            raise BingXLiveTradingDisabled("test-order endpoint requires explicit demo-test enablement")
        request = await self._validated_order(request)
        await self._request(
            "POST", self.ORDER_TEST_PATH, self._order_params(request), signed=True, scope=RateLimitScope.ORDER_CREATE, retry_safe=False
        )

    async def submit_order(self, request: OrderRequest) -> OrderResult:
        self.live_gates.require_all()
        request = await self._validated_order(request)
        try:
            data = await self._request(
                "POST", self.ORDER_PATH, self._order_params(request), signed=True, scope=RateLimitScope.ORDER_CREATE, retry_safe=False
            )
        except (BingXInvalidParameterError, BingXInvalidLeverageError, BingXPositionLimitError):
            self.rule_cache.invalidate(request.symbol)
            raise
        return self._parse_order(data, request.client_order_id)

    async def batch_submit_orders(self, requests: Sequence[OrderRequest]) -> list[OrderResult]:
        self.live_gates.require_all()
        if not requests:
            raise BingXInvalidParameterError("EMPTY_BATCH", "batch must contain orders")
        validated = [await self._validated_order(request) for request in requests]
        import json

        data = await self._request(
            "POST",
            self.BATCH_ORDERS_PATH,
            {"batchOrders": json.dumps([self._order_params(r) for r in validated], separators=(",", ":"))},
            signed=True,
            scope=RateLimitScope.ORDER_CREATE,
            retry_safe=False,
        )
        items = data if isinstance(data, list) else data.get("orders", []) if isinstance(data, dict) else []
        results: list[OrderResult] = []
        for index, request in enumerate(validated):
            results.append(
                self._parse_order(items[index], request.client_order_id)
                if index < len(items)
                else OrderResult(
                    client_order_id=request.client_order_id,
                    exchange_order_id=None,
                    status=OrderStatus.UNKNOWN,
                    reason="BATCH_CHILD_RESULT_MISSING",
                )
            )
        return results

    async def get_order(
        self,
        *,
        symbol: str | None = None,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> OrderResult | None:
        if not order_id and not client_order_id:
            raise BingXInvalidParameterError("ORDER_IDENTIFIER_REQUIRED", "order ID or client order ID is required")
        try:
            data = await self._request(
                "GET",
                self.ORDER_PATH,
                {"symbol": symbol, "orderId": order_id, "clientOrderID": client_order_id},
                signed=True,
                scope=RateLimitScope.ACCOUNT,
            )
        except BingXOrderNotFoundError:
            return None
        return self._parse_order(data, client_order_id or "")

    async def get_order_by_client_id(self, account_id: str, client_order_id: str) -> OrderResult | None:
        return await self.get_order(client_order_id=client_order_id)

    async def open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        data = await self._request("GET", self.OPEN_ORDERS_PATH, {"symbol": symbol}, signed=True, scope=RateLimitScope.ACCOUNT)
        return [self._parse_order(item, str(item.get("clientOrderID", ""))) for item in self._items(data)]

    async def order_history(
        self,
        symbol: str | None = None,
        order_id: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = None,
    ) -> list[OrderResult]:
        data = await self._request(
            "GET",
            self.ALL_ORDERS_PATH,
            {"symbol": symbol, "orderId": order_id, "startTime": start_time, "endTime": end_time, "limit": limit},
            signed=True,
            scope=RateLimitScope.ACCOUNT,
        )
        return [self._parse_order(item, str(item.get("clientOrderID", ""))) for item in self._items(data)]

    async def fills(
        self,
        symbol: str | None = None,
        order_id: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = None,
    ) -> list[Fill]:
        data = await self._request(
            "GET",
            self.FILLS_PATH,
            {"symbol": symbol, "orderId": order_id, "startTime": start_time, "endTime": end_time, "limit": limit},
            signed=True,
            scope=RateLimitScope.ACCOUNT,
        )
        return [self._parse_fill(item) for item in self._items(data)]

    def _parse_fill(self, item: dict[str, Any]) -> Fill:
        return Fill(
            fill_id=str(item.get("tradeId", item.get("id", ""))),
            order_id=str(item["orderId"]) if item.get("orderId") is not None else None,
            client_order_id=str(item["clientOrderID"]) if item.get("clientOrderID") is not None else None,
            symbol=str(item.get("symbol", "")),
            side=Side(str(item.get("side", "BUY")).upper()),
            price=self._decimal(item.get("price", "0"), "fill price"),
            quantity=self._decimal(item.get("qty", item.get("quantity", "0")), "fill quantity"),
            fee=self._decimal(item.get("commission", item.get("fee", "0")), "fee"),
            fee_asset=str(item["commissionAsset"]) if item.get("commissionAsset") else None,
            maker=bool(item["maker"]) if item.get("maker") is not None else None,
            timestamp=int(item.get("time", item.get("timestamp", 0))) or None,
        )

    async def cancel_order(self, account_id: str, client_order_id: str, symbol: str | None = None) -> OrderResult:
        self.live_gates.require_reduction()
        if not symbol:
            raise BingXInvalidParameterError("SYMBOL_REQUIRED", "cancel order requires symbol")
        data = await self._request(
            "DELETE",
            self.ORDER_PATH,
            {"symbol": symbol, "clientOrderID": client_order_id},
            signed=True,
            scope=RateLimitScope.ORDER_CANCEL,
            retry_safe=False,
            risk_reducing=True,
        )
        return self._parse_order(data, client_order_id, fallback_status=OrderStatus.CANCELLED)

    async def batch_cancel_orders(
        self, symbol: str, order_ids: Sequence[str] | None = None, client_order_ids: Sequence[str] | None = None
    ) -> Any:
        self.live_gates.require_reduction()
        import json

        return await self._request(
            "DELETE",
            self.BATCH_ORDERS_PATH,
            {
                "symbol": symbol,
                "orderIdList": json.dumps(list(order_ids or [])),
                "clientOrderIdList": json.dumps(list(client_order_ids or [])),
            },
            signed=True,
            scope=RateLimitScope.ORDER_CANCEL,
            retry_safe=False,
            risk_reducing=True,
        )

    async def cancel_all_orders(self, symbol: str | None = None) -> Any:
        self.live_gates.require_reduction()
        return await self._request(
            "DELETE",
            self.CANCEL_ALL_PATH,
            {"symbol": symbol},
            signed=True,
            scope=RateLimitScope.ORDER_CANCEL,
            retry_safe=False,
            risk_reducing=True,
        )

    async def close_all_positions(self, *, confirmed: bool) -> Any:
        self.live_gates.require_reduction()
        if not confirmed:
            raise BingXRiskRestrictionError("CONFIRMATION_REQUIRED", "emergency close-all requires confirmation")
        return await self._request(
            "POST", self.CLOSE_ALL_PATH, signed=True, scope=RateLimitScope.POSITION_CONTROL, retry_safe=False, risk_reducing=True
        )

    async def close_position(self, position_id: str) -> Any:
        self.live_gates.require_reduction()
        if not position_id:
            raise BingXInvalidParameterError("POSITION_ID_REQUIRED", "position ID is required")
        return await self._request(
            "POST",
            self.CLOSE_POSITION_PATH,
            {"positionId": position_id},
            signed=True,
            scope=RateLimitScope.POSITION_CONTROL,
            retry_safe=False,
            risk_reducing=True,
        )

    async def cancel_all_after(self, countdown_ms: int) -> Any:
        self.live_gates.require_reduction()
        if countdown_ms < 0:
            raise BingXInvalidParameterError("INVALID_COUNTDOWN", "countdown cannot be negative")
        return await self._request(
            "POST",
            self.CANCEL_ALL_AFTER_PATH,
            {"countdownTime": countdown_ms},
            signed=True,
            scope=RateLimitScope.ORDER_CANCEL,
            retry_safe=False,
            risk_reducing=True,
        )

    async def cancel_replace(self, *_: object, **__: object) -> None:
        raise BingXInvalidParameterError(
            "CANCEL_REPLACE_SCHEMA_DISABLED", "cancel/replace is disabled because complete request fields were not supplied"
        )

    async def batch_cancel_replace(self, *_: object, **__: object) -> None:
        raise BingXInvalidParameterError(
            "BATCH_CANCEL_REPLACE_SCHEMA_DISABLED",
            "batch cancel/replace is disabled because complete request fields were not supplied",
        )

    async def adjust_position_margin(self, symbol: str, position_side: PositionSide, amount: Decimal, adjustment_type: int) -> Any:
        self.live_gates.require_all()
        if amount <= 0:
            raise BingXInvalidParameterError("INVALID_MARGIN", "margin amount must be positive")
        return await self._request(
            "POST",
            self.POSITION_MARGIN_PATH,
            {"symbol": symbol, "positionSide": position_side.value, "amount": str(amount), "type": adjustment_type},
            signed=True,
            scope=RateLimitScope.POSITION_CONTROL,
            retry_safe=False,
        )

    async def liquidation_history(self, symbol: str | None = None) -> list[dict[str, Any]]:
        data = await self._request("GET", self.FORCE_ORDERS_PATH, {"symbol": symbol}, signed=True, scope=RateLimitScope.ACCOUNT)
        return self._items(data)

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
            "EXPIRED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
        }
        return OrderResult(
            client_order_id=str(item.get("clientOrderID", item.get("clientOrderId", client_order_id))),
            exchange_order_id=str(item["orderId"]) if item.get("orderId") is not None else None,
            status=status_map.get(str(item.get("status", "")).upper(), fallback_status),
            filled_quantity=Decimal(str(item.get("executedQty", item.get("cumQty", "0")))),
            average_price=Decimal(str(item["avgPrice"])) if item.get("avgPrice") not in {None, "", "0"} else None,
            reason=str(item["errorMsg"]) if item.get("errorMsg") else None,
        )


class BingXCopyTradingClient:
    """Separate optional API surface; schemas are deliberately disabled."""

    async def current_tracks(self) -> None:
        raise UnsupportedCopyTradingOperation("currentTrack")

    async def close_track_order(self) -> None:
        raise UnsupportedCopyTradingOperation("closeTrackOrder")

    async def set_tpsl(self) -> None:
        raise UnsupportedCopyTradingOperation("setTPSL")

    async def spot_trader_sell_order(self) -> None:
        raise UnsupportedCopyTradingOperation("spot trader sellOrder")
