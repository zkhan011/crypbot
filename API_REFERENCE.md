# API reference (current runnable endpoints)

Public telemetry: `GET /health`, `GET /ready`, `GET /metrics`, `GET /api/v1/bingx/readiness`, `GET /api/v1/bingx/market/prices`, `GET /api/v1/trading/dashboard`, `POST /api/v1/trading/mock-scenario/{scenario}`, and `GET /api/v1/trading/reports`. BingX readiness exposes only mode/gate/connectivity state and never credentials or account identifiers. The market-prices endpoint is read-only public BingX data and cannot activate execution.

Protected control-plane endpoints require `Authorization: Bearer <access_token>` returned by `POST /api/v1/auth/login`:

- `GET /api/v1/me`, `POST /api/v1/auth/logout`
- `GET /api/v1/users`, `POST /api/v1/users` (Admin/Super Admin permissions)
- `GET|POST /api/v1/ai/strategy-drafts`
- `POST /api/v1/ai/strategy-drafts/{draft_id}/approve` (Admin/Super Admin)
- `GET /api/v1/audit-logs` (Admin/Super Admin)

The `POST /api/v1/auth/login` payload is `{"email":"superadmin@example.local","password":"ChangeMe123!"}` for local MOCK development. Do not deploy this seed password.
