from dataclasses import dataclass


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
