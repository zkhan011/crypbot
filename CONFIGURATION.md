# CONFIGURATION

Required configuration categories:

- `MODE=MOCK|LIVE`
- `ENABLE_LIVE_TRADING=false` by default
- BingX API key/secret only for live adapter use; withdrawal permission is never required or used.
- Trading pairs, leverage, risk per trade, max daily loss, max drawdown, max open positions.
- Copy trading settings, volume momentum settings, notification preview/live-send settings, and database settings.

Production secrets must be supplied through a secrets manager or environment injection and must never be committed.
