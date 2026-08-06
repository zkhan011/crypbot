from decimal import Decimal
from app.domain.types import OrderStatus, OrderType
from app.exchanges.interfaces import Balance, Candle, OrderBook, OrderBookLevel, OrderRequest, OrderResult, Position, SymbolMetadata


class FakeExchangeClient:
    def __init__(self) -> None:
        self.orders: dict[tuple[str, str], OrderResult] = {}
        self.fail_next_as_unknown = False
        self.reject_symbols: set[str] = set()

    async def symbol_metadata(self, symbol: str) -> SymbolMetadata:
        return SymbolMetadata(
            symbol=symbol,
            min_quantity=Decimal("0.001"),
            quantity_step=Decimal("0.001"),
            tick_size=Decimal("0.1"),
            min_notional=Decimal("5"),
        )

    async def price(self, symbol: str) -> Decimal:
        return Decimal("100")

    async def candles(self, symbol: str, interval: str, limit: int = 100) -> list[Candle]:
        return [
            Candle(
                open_time=index * 60_000,
                open=Decimal("99"),
                high=Decimal("101"),
                low=Decimal("98"),
                close=Decimal("100"),
                volume=Decimal("10"),
            )
            for index in range(limit)
        ]

    async def order_book(self, symbol: str, limit: int = 20) -> OrderBook:
        return OrderBook(
            symbol=symbol,
            bids=[OrderBookLevel(price=Decimal("99.9"), quantity=Decimal("1"))],
            asks=[OrderBookLevel(price=Decimal("100.1"), quantity=Decimal("1"))],
            exchange_timestamp=0,
        )

    async def balances(self, account_id: str) -> list[Balance]:
        return [Balance(asset="USDT", total=Decimal("10000"), available=Decimal("9000"))]

    async def positions(self, account_id: str) -> list[Position]:
        return []

    async def submit_order(self, request: OrderRequest) -> OrderResult:
        if request.symbol in self.reject_symbols:
            return OrderResult(
                client_order_id=request.client_order_id, exchange_order_id=None, status=OrderStatus.REJECTED, reason="FAKE_REJECTED_SYMBOL"
            )
        result = OrderResult(
            client_order_id=request.client_order_id,
            exchange_order_id=f"fx-{len(self.orders) + 1}",
            status=OrderStatus.FILLED if request.order_type == OrderType.MARKET else OrderStatus.SUBMITTED,
            filled_quantity=request.quantity,
            average_price=request.price or Decimal("100"),
        )
        self.orders[(request.account_id, request.client_order_id)] = result
        if self.fail_next_as_unknown:
            self.fail_next_as_unknown = False
            raise TimeoutError("exchange accepted order but response timed out")
        return result

    async def get_order_by_client_id(self, account_id: str, client_order_id: str) -> OrderResult | None:
        return self.orders.get((account_id, client_order_id))

    async def cancel_order(self, account_id: str, client_order_id: str) -> OrderResult:
        existing = self.orders[(account_id, client_order_id)]
        return existing.model_copy(update={"status": OrderStatus.CANCELLED})
