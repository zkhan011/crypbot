# INSTALL

1. Copy `.env.example` to `.env` and keep `MODE=MOCK` / `ENABLE_LIVE_TRADING=false` for demos.
2. Start the local stack with `docker compose up --build`.
3. Open the dashboard at `http://localhost:5173` or API docs at `http://localhost:8000/docs`.
4. MOCK mode requires no BingX API keys and uses deterministic simulated balances, market data, orders, positions, notifications, and reports.
