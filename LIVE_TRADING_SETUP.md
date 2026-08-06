# LIVE TRADING SETUP

LIVE mode is intentionally gated. Before enabling live trading:

1. Complete security, regulatory, exchange, and operational reviews.
2. Verify BingX API keys have no withdrawal permission.
3. Configure IP whitelisting at BingX where available.
4. Set `CRYPBOT_ENABLE_LIVE_TRADING=true` only in the target environment and only after the database-level approval gates pass.
5. Verify risk profile, max daily loss, drawdown, stop-loss, and emergency stop settings.
6. Run reconciliation and controlled paper/demo tests.

The live adapter path is isolated behind interfaces and currently blocks if live trading is not explicitly enabled.

## Credential disclosure response

If a live API key or secret was pasted into chat, an issue, a PR, logs, or any non-secret channel, treat it as compromised. Rotate/revoke it at BingX first; this codebase must not embed or ship disclosed credentials. LIVE startup remains gated by `CRYPBOT_ENABLE_LIVE_TRADING=true`, encrypted verified credentials, approved strategy, risk settings, final administrator confirmation, and audit logging.

## Environment variables are not the BingX credential store

`CRYPBOT_ENABLE_LIVE_TRADING=true` is only an environment-level permission gate. It is not a credential. Do not add BingX API keys or secrets to `production.env.example`, `.env.example`, frontend files, Dockerfiles, GitHub Actions, or Git-tracked configuration. BingX credentials belong in the encrypted credential workflow described in `EXCHANGE_CREDENTIALS.md`.

If you only want production deployment hardening with no real trades, use `CRYPBOT_ENVIRONMENT=production`, `CRYPBOT_EXECUTION_MODE=MOCK`, and `CRYPBOT_ENABLE_LIVE_TRADING=false`.

## Enable and disable procedure

### Disabled (required default)

```text
CRYPBOT_EXECUTION_MODE=MOCK
CRYPBOT_ENABLE_LIVE_TRADING=false
CRYPBOT_BINGX_ENVIRONMENT=DEMO
CRYPBOT_BINGX_DRY_RUN=true
CRYPBOT_BINGX_LIVE_CONFIRMATION=false
BINGX_ENVIRONMENT=DEMO
BINGX_DRY_RUN=true
BINGX_LIVE_TRADING_ENABLED=false
BINGX_LIVE_CONFIRMATION=false
```

Restart the API after changing environment values. This disables the environment gate; the BingX adapter independently refuses order creation/cancellation unless verified credentials, an approved strategy, configured risk limits, and final administrator confirmation are also supplied by the runtime.

### Enabled only after release gates pass

Use a protected deployment secret store, not a committed `.env` file:

```text
CRYPBOT_EXECUTION_MODE=LIVE
CRYPBOT_ENABLE_LIVE_TRADING=true
CRYPBOT_BINGX_ENVIRONMENT=LIVE
CRYPBOT_BINGX_DRY_RUN=false
CRYPBOT_BINGX_LIVE_CONFIRMATION=true
BINGX_ENVIRONMENT=LIVE
BINGX_DRY_RUN=false
BINGX_LIVE_TRADING_ENABLED=true
BINGX_LIVE_CONFIRMATION=true
```

These values only permit the LIVE path to be considered; they do not override the other gates. To disable immediately, trigger the account/global emergency stop first, set `CRYPBOT_ENABLE_LIVE_TRADING=false`, return `CRYPBOT_EXECUTION_MODE=MOCK`, and restart the API/workers. Reconcile exchange orders and positions before resuming any mode.

## Current BingX adapter coverage

The exchange-specific implementation in `backend/app/exchanges/bingx.py` implements the locally supplied perpetual-futures contracts:

- server time, contracts/trading rules, prices, trades, candles, premium/funding, open interest, ticker, best bid/ask and depth;
- balances, positions, income, commission, position mode, margin mode, leverage and liquidation history;
- test/single/batch orders, query/open/history/fills, cancellation, cancel-all, close, position margin and dead-man cancellation;
- corrected-time HMAC signing, typed errors, configurable token buckets, circuit breaker, connection pooling and fail-closed gates;
- configurable WSS transport/recovery with private payloads disabled unless explicitly reviewed.

Withdrawals, transfers, subaccounts, and unrelated products remain outside the bot. Cancel/replace and optional official copy-trading methods fail closed because the supplied endpoint list omitted complete request schemas. Controlled DEMO certification, permission verification, reviewed private WebSocket payloads, and reconciliation soak tests remain release blockers.

The generated endpoint-by-endpoint status is recorded in `docs/bingx-api-coverage.md`. No live or demo network operation was run during implementation.
