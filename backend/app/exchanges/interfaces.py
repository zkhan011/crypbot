from decimal import Decimal
from typing import Protocol
from pydantic import BaseModel
from app.domain.types import OrderStatus, OrderType, Side


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


class MarketDataClient(Protocol):
    async def symbol_metadata(self, symbol: str) -> SymbolMetadata: ...


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
