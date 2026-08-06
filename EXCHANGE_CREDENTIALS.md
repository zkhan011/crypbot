# Exchange credential handling

For the operator procedure, see `BINGX_SECRETS_AND_LIVE_RUNBOOK.md`. It gives the
exact runtime variable names while keeping real values outside Git.

Only trading and market-data permissions are permitted. **Do not create or use withdrawal permissions.** API keys/secrets are encrypted before durable storage and API responses expose only a masked API-key identifier. The raw secret is decrypted only inside a live adapter after all LIVE gates have passed.

Before any future live activation, an authorized administrator must rotate/verify credentials, confirm the exchange account has no withdrawal permission, validate account and market-data access, record a successful verification time, and retain the audit record. The current BingX path is intentionally gated and not certified for real order submission.

## If credentials are accidentally disclosed

Immediately revoke or rotate the disclosed BingX key pair before any deployment. Do not commit it to `.env`, examples, docs, tests, screenshots, or frontend state. After rotation, enter credentials only through the encrypted credential workflow, verify that withdrawal permission is disabled, and retain the audit-chain record for credential creation, verification, and rotation.

## Where to enter BingX API credentials

Do **not** put BingX API keys or secrets in Git-tracked files, `.env.example`, `production.env.example`, frontend code, Docker images, CI logs, screenshots, or documentation. Production environment variables should contain only platform infrastructure secrets such as `CRYPBOT_JWT_SECRET`, `CRYPBOT_CREDENTIAL_MASTER_KEY`, database URL, Redis URL, and live-mode gates.

For production operation, BingX credentials must be entered only through the authenticated exchange-credential workflow after the durable credential API/UI is wired into the runtime. That workflow must:

1. Accept the API key and secret over HTTPS from an authorized tenant administrator or super administrator.
2. Encrypt the raw values immediately with the `CredentialCipher`/`ExchangeCredentialService` envelope-storage path.
3. Persist only the masked key identifier, encryption key id, and ciphertext.
4. Verify account, market-data, balance, and trading permissions while confirming withdrawal permission is disabled.
5. Record credential creation, verification, rotation, and deactivation in the audit hash chain.

Current status: the encrypted credential facade and tenant-scoped repository primitives exist, but the production credential UI/API workflow is not fully wired. Until that workflow is complete, do not load live customer BingX credentials into this application. Continue using MOCK mode.

## How to enable production infrastructure mode safely

Production infrastructure mode is separate from LIVE trading. To run hardened production infrastructure while keeping trading disabled, use protected environment or secret-manager values like this:

```text
CRYPBOT_ENVIRONMENT=production
CRYPBOT_EXECUTION_MODE=MOCK
CRYPBOT_ENABLE_LIVE_TRADING=false
CRYPBOT_SEED_DEMO_USERS=false
CRYPBOT_PRODUCTION_BOOTSTRAP_ADMIN_EMAIL=admin@your-company.example
CRYPBOT_JWT_SECRET=<secret-manager-generated-random-value>
CRYPBOT_CREDENTIAL_MASTER_KEY=<secret-manager-or-kms-managed-key>
CRYPBOT_DATABASE_URL=<postgresql-production-url>
CRYPBOT_REDIS_URL=<redis-production-url>
```

Only after all documented live-readiness gates pass should `CRYPBOT_EXECUTION_MODE=LIVE` and `CRYPBOT_ENABLE_LIVE_TRADING=true` be set in a protected runtime secret store. Even then, live bot start must remain blocked unless verified encrypted credentials, approved strategies, configured risk settings, explicit final confirmation, and audit records are present.

The BingX key and secret are intentionally not accepted as Pydantic `CRYPBOT_BINGX_API_KEY` or `CRYPBOT_BINGX_API_SECRET` settings, where configuration dumps could expose them. The runtime secret provider reads only the exact `BINGX_API_KEY` and `BINGX_API_SECRET` names from protected process injection, redacts its representation, and never persists them. Rotation is performed by updating the secret manager and restarting the API/workers. Tenant-managed encrypted credential ingestion remains a separate incomplete workflow; do not enter live customer keys until permission verification and demo certification are complete.
