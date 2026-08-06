# CONFIGURATION

## Safe exchange defaults

- `CRYPBOT_EXECUTION_MODE=MOCK|LIVE`; default `MOCK`.
- `CRYPBOT_ENABLE_LIVE_TRADING=false`; authoritative environment gate.
- `CRYPBOT_BINGX_ENVIRONMENT=DEMO|LIVE`; default `DEMO`.
- `CRYPBOT_BINGX_DEFAULT_PRODUCT=USDT_M_PERPETUAL`; other products are not implemented yet.
- `CRYPBOT_BINGX_DRY_RUN=true`; must remain enabled until controlled certification is complete.
- `CRYPBOT_BINGX_LIVE_CONFIRMATION=false`; independent final startup confirmation.
- `CRYPBOT_BINGX_BASE_URL`, REST timeout, retry count, receive window, rule-cache TTL, WebSocket stale timeout, and reconciliation interval are shown in `.env.example`.

LIVE startup requires all environment gates plus encrypted verified credentials, approved strategy, configured risk, and runtime administrator confirmation. BingX API credentials are accepted only by the future authenticated encrypted credential workflow; they are deliberately not fields in `.env.example`. Withdrawal permission is never required or used.

## Operational settings

- Trading pairs, leverage, risk per trade, max daily loss, max drawdown, max open positions.
- Copy trading settings, volume momentum settings, notification preview/live-send settings, and database settings.

Production secrets must be supplied through a secrets manager or environment injection and must never be committed.

See `docs/bingx-api-coverage.md` for the exact implemented and unverified exchange surface. Missing product or endpoint configuration must never silently select a different BingX product.
