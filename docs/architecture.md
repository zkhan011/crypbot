# Architecture and phased implementation plan

## Principles

Crypbot prioritizes correctness, security, auditability, reconciliation, and capital protection over speed. All monetary values use Python `Decimal` and database numeric types. HTTP handlers do not call exchanges directly for trading in production paths; domain services own orchestration and risk enforcement.

## Boundaries

- Authentication/RBAC and tenant authorization
- Organizations and users
- Exchange accounts and encrypted credentials
- Exchange interfaces (`ExchangeClient`, `MarketDataClient`, `AccountDataClient`, `OrderExecutionClient`, `ExchangeWebSocketClient`)
- BingX adapter isolated in `backend/app/exchanges/bingx.py`
- Fake exchange for deterministic tests and demos
- Copy-trading engine and state machine
- Independent risk engine
- OMS/order idempotency
- Reconciliation service
- TWAP and volume-aware participation strategies with compliance safeguards
- Audit logging and observability

## Data model

The first migration creates organizations, users, roles, user roles, exchange accounts, encrypted credentials, orders, and append-only audit events. The production target expands this with the full requested trading, reporting, notification, kill-switch, balance, position, and job tables.

## Exchange layer

The trading engine depends on protocols, not BingX classes. New exchanges implement the protocol set. BingX signing uses HMAC-SHA256 canonical query signing documented by BingX; live order placement remains gated pending certification.

## Phases

1. Repository bootstrap, documentation, infrastructure, backend/frontend skeleton.
2. Domain primitives: Decimal rounding, risk engine, copy state machine, TWAP, idempotent order submission, fake exchange.
3. Security: Argon2 password hashing, envelope encryption abstraction, redaction, startup secret validation.
4. Persistence: Alembic migration with tenant-aware core records and audit logs.
5. API and dashboard: health, readiness, metrics, demo workflows, operational dashboard.
6. Tests and CI: unit/integration-style tests for risk, signing, idempotency, tenant-ready schema, and frontend smoke tests.
7. Hardening backlog: complete RBAC APIs, full repository layer, live exchange certification, WebSocket ingestion, KMS adapter, penetration testing, load testing, regulatory review.
