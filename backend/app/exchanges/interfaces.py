from decimal import Decimal
from typing import Protocol
from pydantic import BaseModel
from app.domain.trading_types import OrderStatus, OrderType, PositionSide, Side, TimeInForce


class SymbolMetadata(BaseModel):
    symbol: str
    min_quantity: Decimal
    quantity_step: Decimal
    tick_size: Decimal
    min_notional: Decimal
    max_quantity: Decimal | None = None
    active: bool = True


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
    position_side: PositionSide = PositionSide.BOTH
    time_in_force: TimeInForce | None = None
    working_type: str | None = None
    price_protect: bool | None = None
    close_position: bool = False


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
    position_id: str | None = None
    position_side: PositionSide = PositionSide.BOTH
    available_quantity: Decimal = Decimal("0")
    mark_price: Decimal = Decimal("0")
    margin_type: str | None = None
    liquidation_price: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    update_time: int | None = None


class Trade(BaseModel):
    trade_id: str
    symbol: str
    price: Decimal
    quantity: Decimal
    side: Side | None = None
    timestamp: int | None = None


class PremiumIndex(BaseModel):
    symbol: str
    mark_price: Decimal
    index_price: Decimal
    funding_rate: Decimal | None = None
    next_funding_time: int | None = None


class FundingRate(BaseModel):
    symbol: str
    funding_rate: Decimal
    funding_time: int


class Ticker24h(BaseModel):
    symbol: str
    last_price: Decimal
    price_change: Decimal = Decimal("0")
    price_change_percent: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    quote_volume: Decimal = Decimal("0")


class CommissionRate(BaseModel):
    symbol: str
    maker_rate: Decimal
    taker_rate: Decimal


class IncomeRecord(BaseModel):
    symbol: str | None = None
    income_type: str | None = None
    income: Decimal
    asset: str | None = None
    timestamp: int | None = None


class Fill(BaseModel):
    fill_id: str
    order_id: str | None = None
    client_order_id: str | None = None
    symbol: str
    side: Side
    price: Decimal
    quantity: Decimal
    fee: Decimal = Decimal("0")
    fee_asset: str | None = None
    maker: bool | None = None
    timestamp: int | None = None

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity


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
    async def cancel_order(self, account_id: str, client_order_id: str, symbol: str | None = None) -> OrderResult: ...


class ExchangeClient(MarketDataClient, AccountDataClient, OrderExecutionClient, Protocol):
    pass


class ExchangeWebSocketClient(Protocol):
    async def connect(self) -> None: ...
    async def subscribe_private(self, account_id: str) -> None: ...
