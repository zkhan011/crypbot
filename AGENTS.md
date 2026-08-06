# AGENTS.md

Scope: entire repository.

- Use Python Decimal for all financial calculations; never use floats for money, balances, quantity, PnL, leverage, or risk.
- Keep exchange-specific code behind interfaces in `backend/app/exchanges`.
- Never log secrets; redact keys, signatures, tokens, and decrypted credential material.
- Trading paths must fail closed and pass risk checks before order submission.
- Default execution mode is MOCK simulation. LIVE mode requires multiple explicit gates and is not enabled by default.
