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
