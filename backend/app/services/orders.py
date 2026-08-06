import hashlib
from app.exchanges.interfaces import ExchangeClient, OrderRequest, OrderResult
from app.domain.types import OrderStatus


def deterministic_client_order_id(org_id: str, account_id: str, intent_id: str) -> str:
    return "cb-" + hashlib.sha256(f"{org_id}:{account_id}:{intent_id}".encode()).hexdigest()[:30]


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
            return OrderResult(
                client_order_id=request.client_order_id,
                exchange_order_id=None,
                status=OrderStatus.UNKNOWN,
                reason="SUBMISSION_TIMEOUT_RECONCILE_REQUIRED",
            )
