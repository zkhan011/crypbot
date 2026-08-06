# MOCK DEMO GUIDE

Use the dashboard mock scenario selector to trigger backend behavior for:

- Normal market
- Bullish volume breakout
- Bearish volume breakdown
- Lead trader opens long
- Lead trader opens short
- Lead trader closes position
- Stop-loss hit
- Take-profit hit
- Daily-loss limit hit
- API connection failure
- Order rejection
- High spread / no trade
- Opposite strategy conflict
- Emergency stop

The mock engine simulates BingX balance, prices, candles, order book, volume spikes, lead-trader signals, order placement, fills, positions, stop-loss/take-profit closures, API failures, notification previews, reports, and emergency close-all without real funds.

## Non-trading BingX demo-readiness report

Run `python scripts/validate_bingx_registry.py`, then `python scripts/bingx_demo_certify.py`. The second command creates `artifacts/bingx-demo-certification.json`, contains no credentials, and performs no network mutation. While server-time and demo endpoint contracts remain `BLOCKED_SPEC`, the report intentionally says `certified: false`. Passing `--allow-demo-order` also fails closed until an official demo test-order contract and demo base URL are verified.
