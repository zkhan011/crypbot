# Feature completeness checklist

This checklist is intentionally conservative. **YES** means the current source contains an executable implementation in the local MOCK release; it does not claim production certification. LIVE entries marked **GATED** have a safety boundary/interface but not a certified BingX execution implementation.

| Feature | Backend | Frontend | Mock | Live | RBAC | Tests | Docs | Notes |
|---|---|---|---|---|---|---|---|---|
| MOCK exchange, balance, prices, candles, order book, orders and positions | YES | YES | YES | N/A | N/A | YES | YES | Deterministic fake adapter; no real funds. |
| BingX market data: server time, contracts/rules, prices, trades, candles, premium/funding, OI, ticker/depth | YES | NO | YES | GATED | N/A | YES | YES | Prompt-defined REST contracts and Decimal parsers implemented; controlled DEMO fixtures remain required. |
| BingX balance, positions, income, commission and position controls | YES | NO | YES | GATED | N/A | YES | YES | Signed reads and gated mode/margin/leverage controls implemented. |
| BingX order lifecycle and emergency controls | YES | NO | YES | GATED | N/A | YES | YES | Test/single/batch/query/history/fills/cancel/cancel-all/close/dead-man paths; cancel-replace disabled for missing fields. |
| BingX time sync, retry, typed errors, token buckets and circuit breaker | YES | NO | YES | GATED | N/A | YES | YES | Clock-drift retry and prompt-supplied numeric error mappings implemented; limits are configurable app caps. |
| BingX configurable WebSocket transport and REST recovery | YES | NO | YES | GATED | N/A | YES | YES | Compression, reconnect, dedupe, resubscribe and stale health implemented; private payloads disabled until configured. |
| BingX Decimal order-rule normalization and minimum validation | YES | NO | YES | GATED | N/A | YES | YES | Quantity never rounds up; prices use side-aware ticks; full max/tier rules require verified endpoint fields. |
| Market-data freshness cache | YES | NO | YES | GATED | N/A | YES | YES | Async-safe process-local cache rejects stale/missing snapshots; Redis/global worker coordination remains open. |
| Copy signal and volume-momentum signal paths | YES | YES | YES | GATED | N/A | YES | YES | Six copy-sizing modes; fill-only volume accounting and anti-self-trade controls; never artificial volume. |
| Shared trade risk and emergency stop | YES | YES | YES | GATED | N/A | YES | YES | Existing mock checks are a subset of required production controls. |
| Mock scenario center and notification preview | YES | YES | YES | N/A | N/A | YES | YES | Backend scenario selection is connected to the dashboard. |
| Reports and dashboard telemetry | YES | YES | YES | GATED | N/A | YES | YES | In-memory reports are not durable. |
| Seed users, password hashing, sessions and lockout | YES | YES | YES | NO | YES | YES | YES | In-memory demo control plane; production DB sessions/JWT required. |
| Backend RBAC for user management and AI approvals | YES | Partial | YES | GATED | YES | YES | YES | Roles are enforced on new protected control-plane APIs. |
| AI strategy assistant drafts and approval | YES | YES | YES | NO | YES | YES | YES | Mock provider only; drafts never execute and unsafe draft approvals reject. |
| Telegram notification provider boundary | YES | NO | Preview | GATED | N/A | Partial | YES | SMTP/email provider is not implemented yet. |
| Durable tenant/session/bot/strategy/audit/execution schema | YES | N/A | YES | GATED | Partial | YES | YES | `0004` adds source events, intents, orders, fills, positions, allocations, volume sessions and reconciliation runs. |
| Credential encryption and audit hash-chain primitives | YES | NO | YES | GATED | N/A | YES | YES | Public credential views mask secrets; durable persistence/verification workflow remains required. |
| Full settings CRUD and frontend configuration pages | NO | NO | NO | NO | NO | NO | Partial | Requires durable repositories and authorized APIs. |
| Production-grade multi-bot tenancy, reporting exports, and audit immutability | NO | NO | NO | NO | NO | NO | Partial | Required before customer/live deployment. |

## Required next steps before real-money use

1. Run controlled BingX DEMO fixtures/test-order certification and configure reviewed public/private subscription payloads.
2. Replace in-memory users, sessions, audit events, strategy drafts, orders, and reports with tenant-scoped PostgreSQL repositories and migrations.
3. Add refresh-token rotation, CSRF/cookie controls as applicable, MFA, credential verification (including withdrawal-permission rejection), and independent security review.
4. Add full settings/configuration CRUD, email provider, monitoring, load/failure testing, penetration testing, regulatory review, and controlled live rollout.
