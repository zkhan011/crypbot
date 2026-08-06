# Runbook

- API unavailable: inspect health checks, API logs, database connectivity, and recent deployments.
- Worker unavailable: pause new trading, inspect Redis and worker logs, drain/restart workers.
- Database unavailable: fail closed for new trading, restore service, verify migrations and backups.
- Redis unavailable: disable async job submission and fail closed for trading paths requiring locks.
- BingX unavailable: pause affected exchange accounts and run reconciliation after recovery.
- WebSocket disconnected: pause event-driven copy, reconnect, replay REST reconciliation.
- Unknown order state: mark UNKNOWN, query by client order ID, reconcile before any retry.
- Reconciliation mismatch: create incident, alert operator, apply configured policy.
- Compromised API key: activate account kill switch, revoke key at exchange, rotate credentials, audit access.
- Kill switch: confirm impact, activate platform/org/account/strategy/symbol switch, verify risk rejects new orders.
- Safe shutdown: stop schedulers, drain workers, stop API after readiness fails.
- Restore from backup: restore PostgreSQL, verify checksums, run reconciliation against exchange truth.
- Rollback: deploy prior image and schema-compatible migration plan; do not rollback audit history.

Recommended alerts: API 5xx rate, order rejection spikes, unknown orders, reconciliation mismatches, worker failures, WebSocket reconnect count, kill-switch activation, and credential failures.
