# BingX API coverage and verification ledger

Last reviewed: 2026-08-06

Official documentation requested for review: <https://bingx-api.github.io/docs-v3/#/en>

## Verification limitation

The official documentation site, its GitHub raw-content host, and the GitHub API were all inaccessible from the build environment: each HTTPS request was rejected by the network proxy with HTTP 403, while the configured web-retrieval tool returned HTTP 401. Consequently, this file **does not claim to inventory every current BingX endpoint**. Doing so from memory would violate the requirement not to guess paths, parameters, enums, response fields, or rate limits.

The table below is limited to endpoint contracts already present in this repository. Every row is marked **REQUIRES OFFICIAL VERIFICATION** until it is checked line-by-line against an accessible current documentation snapshot and exercised against a BingX-controlled demo account. Rate limits are deliberately recorded as `UNVERIFIED` rather than invented.

`config/bingx-endpoints.yaml` is the machine-readable source of endpoint status. It is JSON-compatible YAML so `scripts/validate_bingx_registry.py` can validate it using only the Python standard library. All nine current contracts are `BLOCKED_SPEC`; none is represented as officially verified.

## Implemented repository contracts requiring official verification

| Product/module | Method | Path | Authentication | Required parameters used | Optional parameters used | Documented rate limit | Implementation status | Bot usage | Test status |
|---|---:|---|---|---|---|---|---|---|---|
| Perpetual futures market data | GET | `/openApi/swap/v2/quote/contracts` | Public | None | None | UNVERIFIED | Implemented; requires official verification | Symbol rules and precision preflight | Mock transport contract |
| Perpetual futures market data | GET | `/openApi/swap/v2/quote/price` | Public | `symbol` | None | UNVERIFIED | Implemented; requires official verification | Latest/reference price | Mock transport contract |
| Perpetual futures market data | GET | `/openApi/swap/v3/quote/klines` | Public | `symbol`, `interval` | `limit` | UNVERIFIED | Implemented; requires official verification | Volume-momentum candles | Mock transport contract |
| Perpetual futures market data | GET | `/openApi/swap/v2/quote/depth` | Public | `symbol` | `limit` | UNVERIFIED | Implemented; requires official verification | Spread and liquidity snapshot | Mock transport contract |
| Perpetual futures account | GET | `/openApi/swap/v3/user/balance` | Signed API key | `timestamp`, `signature` | `recvWindow` | UNVERIFIED | Implemented; requires official verification | Balance and available-margin checks | Mock transport contract |
| Perpetual futures positions | GET | `/openApi/swap/v2/user/positions` | Signed API key | `timestamp`, `signature` | `recvWindow` | UNVERIFIED | Implemented; requires official verification | Position and reconciliation snapshot | Parser present; dedicated fixture pending |
| Perpetual futures orders | POST | `/openApi/swap/v2/trade/order` | Signed trading key and all platform LIVE gates | `symbol`, `side`, `type`, `quantity`, `clientOrderID`, `timestamp`, `signature` | `price`, `stopPrice`, `reduceOnly`, `recvWindow` | UNVERIFIED | Implemented but LIVE-disconnected and uncertified | Market, limit, stop-market, take-profit-market submission | Mock transport contract only; never live |
| Perpetual futures orders | GET | `/openApi/swap/v2/trade/order` | Signed API key | `clientOrderID`, `timestamp`, `signature` | `recvWindow` | UNVERIFIED | Implemented; requires official verification | Ambiguous-timeout lookup and reconciliation | Parser test pending |
| Perpetual futures orders | DELETE | `/openApi/swap/v2/trade/order` | Signed trading key and all platform LIVE gates | `clientOrderID`, `timestamp`, `signature` | `recvWindow` | UNVERIFIED | Implemented; requires official verification | Cancel one bot-owned order | Contract test pending |

## Requested modules not inventoried or implemented

These areas must remain unavailable until the official documentation can be accessed and exact contracts are added to this ledger. `NO` is intentional and safer than speculative integration.

| Requested module | Inventory complete | Implemented | Reason/status |
|---|---:|---:|---|
| USDT-M perpetual endpoints beyond the table above | NO | NO | Complete current documentation unavailable; exact contracts and limits must be verified. |
| Coin-M perpetual futures | NO | NO | Account/product support and current endpoint contracts are unverified. |
| Spot trading and spot copy trading | NO | NO | Product-specific interfaces and current endpoint contracts are unverified. |
| Perpetual copy-trading account endpoints | NO | NO | Permission model and endpoint contracts are unverified; existing copy engine uses external/mock signals. |
| Fund/account transfers | NO | NO | Not required by current strategy runtime; no endpoint will be added without a documented business need and review. |
| Subaccounts | NO | NO | Current bot does not use subaccounts. |
| Public WebSocket streams | NO | NO | Subscription URL, payloads, compression, heartbeat, and sequence contracts require official verification. |
| Private WebSocket streams | NO | NO | Authentication/listen-key lifecycle and event schemas require official verification. |
| Withdrawals | N/A | **PROHIBITED** | Withdrawal functionality is intentionally excluded and must never be requested by this platform. |

## Implemented non-endpoint safety controls

- Canonical sorted query construction, HMAC-SHA256 signing, millisecond timestamps, API-key header, and receive window.
- HTTPS-only base URL and no secret-bearing logs or exception messages.
- HTTP status plus BingX response-envelope validation.
- Typed authentication, permission, rate-limit, malformed-response, network, and LIVE-gate failures.
- Bounded retries for safe reads; order mutations are never blindly retried.
- Exact `Decimal` parsing and preflight quantity/price/notional normalization that never increases quantity.
- Process-local async market cache with explicit stale-data rejection.
- Idempotent client order identifiers and existing ambiguous-timeout reconciliation through `OrderService`.
- Five adapter gates plus startup gates; LIVE remains disabled by default.
- Tolerant account parsing preserves raw values, normalizes only the supplied `sopt` fixture to internal `spot`, and represents missing/future values safely.
- Exact-name process secret provider for `BINGX_API_KEY`, `BINGX_API_SECRET`, `BINGX_ENVIRONMENT`, `BINGX_BASE_URL`, and `BINGX_RECV_WINDOW`; representations are redacted and secrets are not persisted.
- Atomic midpoint time-offset/single-flight abstraction exists, but no endpoint is connected until the server-time contract and timestamp error code are verified.
- Per-scope rate-limit abstraction blocks openings when limits are unknown while preserving separately reviewed cancellation capacity; current documented values remain unavailable.
- Circuit breaker blocks exposure increases after repeated failures while allowing callers to designate risk-reducing recovery operations.

## Coverage totals

| Product | Registry contracts | Verified | `BLOCKED_SPEC` | Live enabled |
|---|---:|---:|---:|---:|
| USDT-M perpetual | 9 | 0 | 9 | NO |
| Coin-M perpetual | 0 | 0 | 0 | NO |
| Spot | 0 | 0 | 0 | NO |
| Perpetual copy-trading API | 0 | 0 | 0 | NO |
| Spot copy-trading API | 0 | 0 | 0 | NO |
| Public/private WebSocket | 0 | 0 | 0 | NO |

## Required completion procedure

1. Obtain an immutable current official documentation snapshot and record its retrieval date/commit or release identifier.
2. Inventory every endpoint directly from that snapshot, including exact parameters, enums, response schema, permission scope, deprecation state, and rate limit.
3. Review each implemented row above and correct any mismatch before enabling its feature.
4. Add sanitized response fixtures and parser tests for every bot-used endpoint.
5. Add endpoint-scoped, documented rate-limit buckets with emergency cancellation/close capacity.
6. Implement server-time synchronization and one-time drift recovery only after verifying the current server-time endpoint and drift error code.
7. Implement WebSockets only after verifying URLs, subscription/authentication payloads, compression, heartbeat, sequence, and recovery contracts.
8. Certify in a BingX demo environment with test orders only. Automated tests must never place live orders.

Until these steps are complete, the feature matrix must continue to label LIVE BingX support as **GATED / NOT CERTIFIED**.

## Phased outstanding implementation checklist

- [x] Preserve existing exchange interfaces, fake adapter, strategy services, idempotency, risk checks, and LIVE gates.
- [x] Add machine-readable endpoint registry and registry/ledger validation.
- [x] Add tolerant supplied `sopt` fixture parsing and safe unknown/missing account types.
- [x] Add credential redaction, exact environment-name loading, URL/environment guards, and automated-LIVE refusal.
- [x] Add contract-independent midpoint time-offset, single-flight refresh, fail-closed rate-limit, circuit-breaker, Decimal preflight, and stale-cache primitives.
- [x] Add sanitized non-trading demo-readiness report; current result intentionally not certified.
- [ ] `BLOCKED_SPEC`: verify server-time endpoint path, response field, timestamp error codes, and retry rule; then connect the time synchronizer.
- [ ] `BLOCKED_SPEC`: verify rate-limit scopes/values and `Retry-After` behavior; then configure distributed Redis buckets.
- [ ] `BLOCKED_SPEC`: verify and fixture every market/account/position/order parser in the registry.
- [ ] `BLOCKED_SPEC`: inventory and implement bot-required open-order, history, fills, batch/cancel-all, test-order, close, and emergency endpoints.
- [ ] `BLOCKED_SPEC`: verify public/private WebSocket URLs, auth/subscription schema, compression, heartbeat, sequence, and recovery behavior.
- [ ] `BLOCKED_SPEC`: inventory official perpetual/spot copy-trading permissions and contracts.
- [ ] `BLOCKED_SPEC`: inventory separate spot and Coin-M contracts; keep both clients inactive until configured and certified.
- [ ] Implement durable unfinished-order/fill/validation persistence and startup/periodic reconciliation after read contracts are verified.
- [ ] Connect stale market cache, circuit state, and reconciled readiness to strategy opening checks across workers.
- [ ] Run read-only BingX demo certification, sanitized fixture capture, official test order, and an explicitly approved minimal demo-only lifecycle.
- [ ] Run all backend/frontend/container tests, reconciliation/failure soak tests, security review, and operational sign-off.
