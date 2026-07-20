# Production readiness checklist

**Status: NOT READY FOR REAL MONEY OR CUSTOMER CREDENTIALS.** This document is a release gate, not a promise.

| Area | Status | Required closure |
|---|---|---|
| Identity and RBAC | Partial | Replace the MOCK in-memory control plane with PostgreSQL repositories, refresh rotation, MFA, password reset, and session revocation. |
| Tenant isolation | Schema foundation | Apply migration `0002`, implement tenant-scoped repositories/API policies, and prove isolation under integration tests. |
| Settings persistence | Schema foundation | Add versioned settings CRUD and wire strategy reloads to persisted records. |
| Credential security | Partial | Use a managed KMS, verify BingX permissions, and add credential lifecycle UI/API. |
| BingX adapter | Gated skeleton | Complete official endpoint contracts, DEMO certification, reconciliation, rate-limit and websocket recovery tests. |
| Live trading gates | Partial | Require verified credentials, approved+mock-tested strategy, risk profile, final confirmation, and durable audit event. |
| AI safety | Partial | Draft-only mock flow exists; add durable storage, validation runs, provider controls, and request limits. |
| Audit integrity | Partial | Hash-chain primitive/schema exists; persist append-only entries and verify externally during operations. |
| Notifications | Partial | Mock/Telegram boundary exists; add encrypted SMTP/Telegram settings, delivery jobs, retries, and monitoring. |
| Deployment and backup | Partial | Provision secrets, TLS, least-privilege containers, tested backup/restore, monitoring, alerting, and incident drills. |
| Security/legal review | Not started | Penetration test, threat model, dependency review, regulatory assessment, and controlled pilot are mandatory. |
