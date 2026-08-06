import hashlib
from decimal import Decimal
from app.exchanges.interfaces import ExchangeClient, OrderRequest, OrderResult
from app.domain.trading_types import OrderStatus


def deterministic_client_order_id(org_id: str, account_id: str, intent_id: str) -> str:
    return "cb-" + hashlib.sha256(f"{org_id}:{account_id}:{intent_id}".encode()).hexdigest()[:30]


def deterministic_strategy_order_id(
    strategy: str,
    account_id: str,
    source_event_id: str,
    symbol: str,
    action: str,
    sequence: int,
) -> str:
    if sequence < 0 or not all((strategy, account_id, source_event_id, symbol, action)):
        raise ValueError("complete deterministic order identity is required")
    identity = f"{strategy}:{account_id}:{source_event_id}:{symbol}:{action}:{sequence}"
    return "cb-" + hashlib.sha256(identity.encode()).hexdigest()[:30]


class OrderService:
    def __init__(self, exchange: ExchangeClient):
        self.exchange = exchange

    async def submit_idempotent(self, request: OrderRequest) -> OrderResult:
        existing = await self.exchange.get_order_by_client_id(request.account_id, request.client_order_id)
        if existing:
            return existing
        try:
            return await self.exchange.submit_order(request)
        except TimeoutError:
            known = await self.exchange.get_order_by_client_id(request.account_id, request.client_order_id)
            if known:
                return known
            for method_name in ("open_orders", "order_history"):
                method = getattr(self.exchange, method_name, None)
                if method is not None:
                    for candidate in await method(symbol=request.symbol):
                        if isinstance(candidate, OrderResult) and candidate.client_order_id == request.client_order_id:
                            return candidate
            fills_method = getattr(self.exchange, "fills", None)
            if fills_method is not None:
                fills = [fill for fill in await fills_method(symbol=request.symbol) if fill.client_order_id == request.client_order_id]
                if fills:
                    total_quantity = sum((fill.quantity for fill in fills), Decimal("0"))
                    total_notional = sum((fill.price * fill.quantity for fill in fills), Decimal("0"))
                    return OrderResult(
                        client_order_id=request.client_order_id,
                        exchange_order_id=fills[0].order_id,
                        status=OrderStatus.FILLED,
                        filled_quantity=total_quantity,
                        average_price=total_notional / total_quantity,
                        reason="RECOVERED_FROM_FILLS_AFTER_TIMEOUT",
                    )
            return OrderResult(
                client_order_id=request.client_order_id,
                exchange_order_id=None,
                status=OrderStatus.UNKNOWN,
                reason="SUBMISSION_TIMEOUT_RECONCILE_REQUIRED",
            )
