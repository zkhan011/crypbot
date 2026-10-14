from dataclasses import dataclass
from typing import Protocol

from app.exchanges.interfaces import Fill, OrderResult, Position


@dataclass(frozen=True)
class ReconciliationIncident:
    category: str
    resource_id: str
    details: str


class ReconciliationService:
    def compare_orders(self, local_client_ids: set[str], exchange_client_ids: set[str]) -> list[ReconciliationIncident]:
        incidents = []
        for cid in sorted(local_client_ids - exchange_client_ids):
            incidents.append(ReconciliationIncident("Local order missing on exchange", cid, "local order was not found at exchange"))
        for cid in sorted(exchange_client_ids - local_client_ids):
            incidents.append(ReconciliationIncident("Exchange order missing locally", cid, "exchange order was not found locally"))
        return incidents


class ReconciliationExchange(Protocol):
    async def open_orders(self, symbol: str | None = None) -> list[OrderResult]: ...
    async def order_history(self, symbol: str | None = None, **kwargs: object) -> list[OrderResult]: ...
    async def fills(self, symbol: str | None = None, **kwargs: object) -> list[Fill]: ...
    async def positions(self, account_id: str, symbol: str | None = None) -> list[Position]: ...


@dataclass(frozen=True)
class StartupReconciliationResult:
    ready_for_opening: bool
    incidents: list[ReconciliationIncident]
    exchange_open_orders: list[OrderResult]
    exchange_positions: list[Position]
    recent_fills: list[Fill]


class StartupReconciliationService:
    """Fail-closed startup comparison; it never submits or mutates orders."""

    async def reconcile(
        self,
        exchange: ReconciliationExchange,
        account_id: str,
        unfinished_client_ids: set[str],
        known_position_ids: set[str],
    ) -> StartupReconciliationResult:
        open_orders = await exchange.open_orders()
        history = await exchange.order_history()
        fills = await exchange.fills()
        positions = await exchange.positions(account_id)
        exchange_ids = {order.client_order_id for order in [*open_orders, *history] if order.client_order_id}
        incidents = ReconciliationService().compare_orders(unfinished_client_ids, exchange_ids)
        for position in positions:
            if position.position_id and position.position_id not in known_position_ids:
                incidents.append(
                    ReconciliationIncident(
                        "Unknown exchange position",
                        position.position_id,
                        f"manual review required for {position.symbol}",
                    )
                )
        return StartupReconciliationResult(
            ready_for_opening=not incidents,
            incidents=incidents,
            exchange_open_orders=open_orders,
            exchange_positions=positions,
            recent_fills=fills,
        )
