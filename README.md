# Crypbot

Crypbot is a modular-monolith cryptocurrency copy-trading and compliant automated execution platform. The initial runnable release defaults to the deterministic fake exchange in `MOCK` mode; BingX perpetual futures support is isolated behind exchange interfaces for future certified live integration.

> Safety warning: this repository is not production-ready for real funds. Before LIVE use it requires security review, legal/regulatory review, exchange certification, penetration testing, load testing, disaster-recovery drills, and controlled live trials.

## Architecture summary

- FastAPI backend with Pydantic v2 contracts and explicit domain services for risk, copy-trading, TWAP simulation, reconciliation, encrypted credentials, and exchange adapters.
- PostgreSQL schema via Alembic with tenant identifiers on trading and audit tables.
- Redis is included for worker/lock evolution; the initial worker image runs the same app dependencies.
- React/Vite/TanStack Query administration dashboard with a prominent MOCK indicator.
- Docker Compose includes API, worker, scheduler, PostgreSQL, Redis, frontend, Nginx, Prometheus, and Grafana.

## Local prerequisites

- Docker and Docker Compose
- Python 3.12 for local backend commands
- Node.js 20+ for local frontend commands

## Startup commands

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000/docs  
Dashboard: http://localhost:5173

## Migration commands

```bash
cd backend
alembic upgrade head
```

## Seed commands

```bash
python scripts/seed_dev.py
```

The seed command creates a clearly identified local development administrator only; no production users are hardcoded.

## Test commands

```bash
cd backend && python -m pytest
cd frontend && npm test
```

## Simulation workflow

```bash
curl -X POST http://localhost:8000/api/v1/demo/copy-trade
curl -X POST http://localhost:8000/api/v1/demo/submit-order
curl -X POST http://localhost:8000/api/v1/demo/twap
curl http://localhost:8000/api/v1/reconciliation/demo
```

## Demo workflow

DEMO exchange mode is a configuration target, not enabled by default. It must be explicitly configured and certified with exchange-provided test/demo credentials where available.

## Live-mode restrictions

LIVE mode requires environment enablement, database enablement, platform administrator approval, organization administrator approval, verified non-withdrawal credentials, assigned risk profile, recent reconciliation, healthy market data/workers, and UI confirmation. The code intentionally does not submit BingX live orders in this initial release.

## Troubleshooting

- API unavailable: check `docker compose logs api` and `/health`.
- Database unavailable: check PostgreSQL container health and `DATABASE_URL`.
- Redis unavailable: check Redis container health and worker logs.
- Unknown order: call reconciliation before resubmitting.

## Project status

Initial runnable release with deterministic fake exchange, safety controls, documentation, tests, CI, and BingX connector skeleton. Not approved for real-money production use.
