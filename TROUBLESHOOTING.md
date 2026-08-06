# Troubleshooting

If the dashboard cannot load, check `GET /health`, browser network requests, and reverse-proxy routing. For a local API run, use `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000` and run the Vite frontend separately.

If protected actions return 401, sign in through the dashboard panel and retry. If they return 403, use a role with the required permission. Five failed login attempts lock an account for 15 minutes in the in-memory demo; restart only in local development to reset it.

If a mock order is rejected, inspect the dashboard risk events and select a normal-market scenario before retrying. If an emergency stop is active, restart/reset the mock bot rather than attempting to bypass risk controls.

If BingX startup reports an environment mismatch, do not bypass it. Confirm that `BINGX_ENVIRONMENT`, `BINGX_BASE_URL`, `CRYPBOT_BINGX_DRY_RUN`, and the allowlist belong to the same verified environment. Unknown demo URLs intentionally fail closed. Run `python scripts/validate_bingx_registry.py` to detect registry/ledger drift and `python scripts/bingx_demo_certify.py` for a sanitized non-trading readiness report.

Authentication, permission, timestamp, rate-limit, and malformed-response failures must be handled using `docs/bingx-errors.md`. Never paste signed URLs, headers, credentials, or raw private responses into tickets.
