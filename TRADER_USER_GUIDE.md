# Trader guide (MOCK release)

MOCK mode simulates market data, lead-trader signals, orders, fills, P&L, risk events, notifications, and reports without BingX credentials or funds. Select a scenario such as **Lead trader opens long** or **Bullish volume breakout**; this invokes backend strategy and risk code rather than changing UI text only.

The volume feature is a legitimate volume-momentum signal simulation. It does not generate volume, match controlled accounts, or guarantee outcomes. Use the emergency close-all control to close mock positions and fail closed for further mock trading.

AI drafts are recommendations only. A Trader can request a draft but cannot approve it. Approved drafts still require mock validation and further controlled authorization before any future live activation.
