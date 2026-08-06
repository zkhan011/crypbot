# Deployment notes

For local simulation, follow `INSTALL.md`. Docker Compose provisions the API, frontend, PostgreSQL, Redis, worker, scheduler, and reverse proxy scaffolding. Customer infrastructure should run on Ubuntu with 2–4 CPU cores, 4–8 GB RAM, a stable network, persistent encrypted backups, and a static outbound IP suitable for exchange allowlisting.

Do not enable LIVE execution until the BingX connector has been completed and certified, credentials have been verified as trading-only (no withdrawal permission), tenant persistence is enabled, reconciliation is healthy, and a controlled approval process has passed. See `LIVE_TRADING_SETUP.md` and `FEATURE_CHECKLIST.md`.
