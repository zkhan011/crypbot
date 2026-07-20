# LIVE TRADING SETUP

LIVE mode is intentionally gated. Before enabling live trading:

1. Complete security, regulatory, exchange, and operational reviews.
2. Verify BingX API keys have no withdrawal permission.
3. Configure IP whitelisting at BingX where available.
4. Set `ENABLE_LIVE_TRADING=true` only in the target environment.
5. Verify risk profile, max daily loss, drawdown, stop-loss, and emergency stop settings.
6. Run reconciliation and controlled paper/demo tests.

The live adapter path is isolated behind interfaces and currently blocks if live trading is not explicitly enabled.
