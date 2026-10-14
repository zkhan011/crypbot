# AI Strategy Assistant

`MockAIProviderAdapter` supplies deterministic demonstration drafts without external AI credentials. It returns structured COPY, VOLUME, or HYBRID strategy data with pairs, leverage, loss limits, stop-loss/take-profit guidance, required mock scenarios, and an `activationStatus` of `DRAFT`.

The assistant has no order-execution dependency. It cannot bypass the shared risk engine. A protected Admin/Super Admin approval API rejects the deliberately risky mock draft (50x leverage or no stop loss). Production AI integration must add provider authentication, tenant storage, prompt/response retention controls, request rate limiting, review tooling, and a full strategy validation suite before it is enabled.
