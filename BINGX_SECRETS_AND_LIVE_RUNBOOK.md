# BingX secret injection and LIVE runbook

> **Current release status: LIVE execution is not certified and must remain disabled.**
> This file explains where the runtime reads credentials and how an operator will
> activate LIVE only after every release gate in
> `PRODUCTION_READINESS_CHECKLIST.md` has been closed. It is not authorization to
> trade real funds.

## Where to provide the API key and secret

The backend reads exactly these two **process environment variables**:

```text
BINGX_API_KEY
BINGX_API_SECRET
```

Do not add them to source code, `.env.example`, `production.env.example`, a
Dockerfile, Compose YAML, frontend configuration, CI output, or any Git-tracked
file. Never paste a real value into a command retained in shell history.

Use one of these protected injection methods:

1. **Production secret manager (recommended):** map the two secrets to the API
   and worker process environment using workload identity and least privilege.
2. **Container orchestrator:** use Docker/Kubernetes secret support and expose
   the values only to backend and worker containers, never to the frontend.
3. **Temporary operator test:** use an untracked file outside this repository,
   owned by the service user and mode `0600`. Do not use this for customer
   production deployments.

Example temporary file creation (placeholders only):

```bash
install -m 600 /dev/null /run/crypbot/bingx.env
${EDITOR:-vi} /run/crypbot/bingx.env
```

The protected file contains:

```text
BINGX_API_KEY=<read-from-secret-manager>
BINGX_API_SECRET=<read-from-secret-manager>
```

Load it without echoing either value:

```bash
set -a
. /run/crypbot/bingx.env
set +a
python scripts/validate_bingx_config.py
```

The validator reports only whether a complete pair exists. Delete the temporary
file and rotate the key after testing.

## BingX key permissions

Create a dedicated, IP-allowlisted key with the narrowest permissions needed:

- market-data/read access;
- balance, position, order, and fill read access;
- futures trading only after controlled DEMO certification and release approval;
- **no withdrawal permission**.

Do not reuse a personal or withdrawal-capable key. If a key appeared in chat, an
issue, logs, terminal output, or Git history, revoke it before proceeding.

## Keep LIVE disabled now

Use this configuration while completing DEMO certification:

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

Run the non-trading checks:

```bash
python scripts/validate_bingx_config.py
python scripts/bingx_demo_certify.py
cd backend
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. pytest -q
```

Do not proceed while the certification report says `"certified": false`.

## Future LIVE activation procedure

Do not set LIVE values until all of these are true:

- controlled BingX DEMO certification passed;
- durable permission verification confirms no withdrawal access;
- startup reconciliation completed without unresolved exchange state;
- the strategy is approved and passed its MOCK test;
- durable risk settings cover leverage, exposure, stop-loss, daily loss, fees,
  spread, slippage, and drawdown;
- emergency cancel-all and reduce-only close were exercised in DEMO;
- audit verification, monitoring, alerts, backup/restore, penetration testing,
  incident review, and final administrator approval are complete.

Only after those gates pass, inject credentials through the secret manager and
set all gates in the protected runtime environment:

```text
CRYPBOT_EXECUTION_MODE=LIVE
CRYPBOT_ENABLE_LIVE_TRADING=true
CRYPBOT_BINGX_ENVIRONMENT=LIVE
CRYPBOT_BINGX_DRY_RUN=false
CRYPBOT_BINGX_LIVE_CONFIRMATION=true
BINGX_ENVIRONMENT=LIVE
BINGX_BASE_URL=https://open-api.bingx.com
BINGX_DRY_RUN=false
BINGX_LIVE_TRADING_ENABLED=true
BINGX_LIVE_CONFIRMATION=true
```

Then run configuration validation, migrations, startup reconciliation, read-only
connectivity checks, and health/readiness checks before starting a strategy.
These flags do not bypass credential verification, strategy approval, risk
configuration, reconciliation, final confirmation, or audit recording.

## Emergency disable

1. Trigger emergency stop and cancel open orders through the authenticated
   control plane.
2. Use reduce-only closing where safely required and verify exchange state.
3. Set `CRYPBOT_ENABLE_LIVE_TRADING=false`,
   `BINGX_LIVE_TRADING_ENABLED=false`, and `BINGX_DRY_RUN=true` in the protected
   deployment configuration.
4. Restart API and workers, then reconcile balances, positions, orders, history,
   and fills.
5. Rotate credentials if compromise is suspected and preserve the audit trail.

LIVE must not be started from the current repository state because its readiness
checklist still contains unresolved real-money release blockers.

The backend enforces this statement through `ProductionReadinessGate`. A
structurally valid production process can start for read-only diagnostics, but
it reports `LIVE_PAUSED` and rejects opening orders until every server-derived
check passes. Environment flags are not readiness evidence and there is no
supported override variable.

## Troubleshooting prices versus LIVE activation

Public market prices and order execution are separate. Prices require no API key
and are exposed by `GET /api/v1/bingx/market/prices` when
`CRYPBOT_BINGX_PUBLIC_MARKET_DATA_ENABLED=true`. Check the backend's outbound TLS
access to `https://open-api.bingx.com` if that endpoint returns `503`.

`GET /api/v1/bingx/readiness` reports `CONNECTED_READ_ONLY` after a successful
price request. It also reports `adapter_runtime_connected=false` because the
durable credential/risk/approval/reconciliation strategy runtime is not yet
wired. LIVE activation therefore remains intentionally blocked rather than
claiming that environment flags alone started real-money execution.
