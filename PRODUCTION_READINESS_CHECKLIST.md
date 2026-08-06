# Production readiness checklist

**Status: NOT READY FOR REAL MONEY OR CUSTOMER CREDENTIALS.** This document is a release gate, not a promise.

| Area | Status | Required closure |
|---|---|---|
| Identity and RBAC | Partial | Tenant-scoped repository primitives exist; wire durable auth/session repositories into API runtime, then add refresh rotation, MFA, password reset, and session revocation. |
| Tenant isolation | Partial | Tenant-scoped bot/settings/credential repositories exist; apply migrations and enforce tenant context across every protected API with PostgreSQL integration tests. |
| Settings persistence | Schema foundation | Add versioned settings CRUD and wire strategy reloads to persisted records. |
| Credential security | Partial | Tenant-scoped encrypted credential repository and live-gate evaluator exist; use a managed KMS and add verified BingX lifecycle UI/API. |
| BingX adapter | Gated controlled-demo candidate | 47 prompt-supplied endpoint contracts are registered; market/account/order parsers, time sync, typed errors, token buckets, circuit breaker, configurable WebSocket transport, persistence migration, and startup reconciliation exist. Controlled DEMO certification and private subscription payload review remain required. |
| Live trading gates | Partial | Require verified credentials, approved+mock-tested strategy, risk profile, final confirmation, and durable audit event. |
| AI safety | Partial | Draft-only mock flow exists; add durable storage, validation runs, provider controls, and request limits. |
| Audit integrity | Partial | Hash-chain primitive/schema exists; persist append-only entries and verify externally during operations. |
| Notifications | Partial | Mock/Telegram boundary exists; add encrypted SMTP/Telegram settings, delivery jobs, retries, and monitoring. |
| Deployment and backup | Partial | Provision secrets, TLS, least-privilege containers, tested backup/restore, monitoring, alerting, and incident drills. |
| Security/legal review | Not started | Penetration test, threat model, dependency review, regulatory assessment, and controlled pilot are mandatory. |

## Credential safety update

- [x] Canonical environment gate documented as `CRYPBOT_ENABLE_LIVE_TRADING=false` by default.
- [x] Repository secret scanner added to CI to block likely committed raw credentials.
- [ ] Production live trading remains incomplete until credential UI/API workflow, exchange permission verification, certified BingX order endpoints, reconciliation jobs, penetration testing, and controlled live testing are finished.

## Production mode versus LIVE trading

Production infrastructure mode can be configured with `CRYPBOT_ENVIRONMENT=production` while leaving `CRYPBOT_EXECUTION_MODE=MOCK` and `CRYPBOT_ENABLE_LIVE_TRADING=false`. This is the recommended customer-infrastructure smoke-test posture.

LIVE trading is still blocked unless the encrypted credential UI/API workflow, BingX permission verification, approved strategy checks, durable risk settings, final confirmation, reconciliation, monitoring, and audit gates are completed and tested.

## Controlled demo gate

- [x] Machine-readable endpoint registry validates against the coverage ledger.
- [x] Non-trading certification report is repeatable and sanitized.
- [x] Unknown endpoint limits block opening capacity rather than using invented limits.
- [x] Unknown demo URL is not allowlisted.
- [x] Implement prompt-supplied server-time, market, account, position-control, and order endpoint contracts.
- [x] Implement typed prompt-supplied error-code mappings with unknown fallback.
- [ ] Configure and review a separate BingX demo base URL and credentials.
- [ ] Validate prompt-supplied parsers with sanitized BingX DEMO responses.
- [ ] Add read-only connection/authentication certification with sanitized fixtures.
- [ ] Add official test-order certification; no demo mutation before explicit review.
