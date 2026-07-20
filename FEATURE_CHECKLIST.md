# Feature completeness checklist

This checklist is intentionally conservative. **YES** means the current source contains an executable implementation in the local MOCK release; it does not claim production certification. LIVE entries marked **GATED** have a safety boundary/interface but not a certified BingX execution implementation.

| Feature | Backend | Frontend | Mock | Live | RBAC | Tests | Docs | Notes |
|---|---|---|---|---|---|---|---|---|
| MOCK exchange, balance, prices, candles, order book, orders and positions | YES | YES | YES | N/A | N/A | YES | YES | Deterministic fake adapter; no real funds. |
| BingX live adapter boundary and explicit environment gate | YES | NO | N/A | GATED | N/A | YES | YES | Real endpoint coverage/certification remains required. |
| Copy signal and volume-momentum signal paths | YES | YES | YES | GATED | N/A | YES | YES | Volume logic uses market signals only, never artificial volume. |
| Shared trade risk and emergency stop | YES | YES | YES | GATED | N/A | YES | YES | Existing mock checks are a subset of required production controls. |
| Mock scenario center and notification preview | YES | YES | YES | N/A | N/A | YES | YES | Backend scenario selection is connected to the dashboard. |
| Reports and dashboard telemetry | YES | YES | YES | GATED | N/A | YES | YES | In-memory reports are not durable. |
| Seed users, password hashing, sessions and lockout | YES | YES | YES | NO | YES | YES | YES | In-memory demo control plane; production DB sessions/JWT required. |
| Backend RBAC for user management and AI approvals | YES | Partial | YES | GATED | YES | YES | YES | Roles are enforced on new protected control-plane APIs. |
| AI strategy assistant drafts and approval | YES | YES | YES | NO | YES | YES | YES | Mock provider only; drafts never execute and unsafe draft approvals reject. |
| Telegram notification provider boundary | YES | NO | Preview | GATED | N/A | Partial | YES | SMTP/email provider is not implemented yet. |
| Database persistence and migrations | Partial | N/A | NO | Partial | Partial | Partial | YES | Schema scaffold exists; runtime uses memory, so customer deployment is incomplete. |
| Full settings CRUD and frontend configuration pages | NO | NO | NO | NO | NO | NO | Partial | Requires durable repositories and authorized APIs. |
| Production-grade multi-bot tenancy, reporting exports, and audit immutability | NO | NO | NO | NO | NO | NO | Partial | Required before customer/live deployment. |

## Required next steps before real-money use

1. Implement and certify BingX REST/WebSocket calls using current official documentation and a controlled DEMO environment.
2. Replace in-memory users, sessions, audit events, strategy drafts, orders, and reports with tenant-scoped PostgreSQL repositories and migrations.
3. Add refresh-token rotation, CSRF/cookie controls as applicable, MFA, credential verification (including withdrawal-permission rejection), and independent security review.
4. Add full settings/configuration CRUD, email provider, monitoring, load/failure testing, penetration testing, regulatory review, and controlled live rollout.
