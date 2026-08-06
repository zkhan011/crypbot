from decimal import Decimal
from typing import Protocol
from pydantic import BaseModel
from app.domain.trading_types import OrderStatus, OrderType, Side


class SymbolMetadata(BaseModel):
    symbol: str
    min_quantity: Decimal
    quantity_step: Decimal
    tick_size: Decimal
    min_notional: Decimal


class OrderRequest(BaseModel):
    account_id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    client_order_id: str
    price: Decimal | None = None
    trigger_price: Decimal | None = None
    reduce_only: bool = False


class OrderResult(BaseModel):
    client_order_id: str
    exchange_order_id: str | None
    status: OrderStatus
    filled_quantity: Decimal = Decimal("0")
    average_price: Decimal | None = None
    reason: str | None = None


class Balance(BaseModel):
    asset: str
    total: Decimal
    available: Decimal


class Position(BaseModel):
    symbol: str
    side: Side
    quantity: Decimal
    entry_price: Decimal
    leverage: Decimal


class Candle(BaseModel):
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class OrderBookLevel(BaseModel):
    price: Decimal
    quantity: Decimal


class OrderBook(BaseModel):
    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    exchange_timestamp: int | None = None


class MarketDataClient(Protocol):
    async def symbol_metadata(self, symbol: str) -> SymbolMetadata: ...
    async def price(self, symbol: str) -> Decimal: ...
    async def candles(self, symbol: str, interval: str, limit: int = 100) -> list[Candle]: ...
    async def order_book(self, symbol: str, limit: int = 20) -> OrderBook: ...


class AccountDataClient(Protocol):
    async def balances(self, account_id: str) -> list[Balance]: ...
    async def positions(self, account_id: str) -> list[Position]: ...


class OrderExecutionClient(Protocol):
    async def submit_order(self, request: OrderRequest) -> OrderResult: ...
    async def get_order_by_client_id(self, account_id: str, client_order_id: str) -> OrderResult | None: ...
    async def cancel_order(self, account_id: str, client_order_id: str) -> OrderResult: ...


class ExchangeClient(MarketDataClient, AccountDataClient, OrderExecutionClient, Protocol):
    pass


class ExchangeWebSocketClient(Protocol):
    async def connect(self) -> None: ...
    async def subscribe_private(self, account_id: str) -> None: ...
