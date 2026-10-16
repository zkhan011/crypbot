# BingX incident and emergency-stop procedure

1. Trigger the account and global kill switches.
2. Pause copy and volume strategies; prevent all new/increasing exposure.
3. Preserve verified cancellation and reduce-only capacity where the exchange is reachable.
4. Cancel bot-owned open orders using persisted client/exchange IDs; never issue broad unverified mutations.
5. Reconcile local unfinished orders, exchange open orders, fills, and positions.
6. Escalate unknown exchange positions/orders for manual review; do not reopen strategies.
7. Set `CRYPBOT_ENABLE_LIVE_TRADING=false`, `CRYPBOT_EXECUTION_MODE=MOCK`, `BINGX_ENVIRONMENT=DEMO`, and restart API/workers.
8. Rotate credentials after suspected disclosure and verify that withdrawal permission was never enabled.
9. Preserve sanitized audit/correlation records, never signed URLs or raw secrets.
10. Resume only after root-cause review, successful reconciliation, risk approval, and controlled demo recertification.

Current limitation: cancel-all and emergency reduce-only exchange endpoint contracts are `BLOCKED_SPEC`. Until verified, the platform must remain in MOCK and operators must use the exchange's authenticated console for emergency account action.
