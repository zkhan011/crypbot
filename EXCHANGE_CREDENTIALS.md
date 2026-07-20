# Exchange credential handling

Only trading and market-data permissions are permitted. **Do not create or use withdrawal permissions.** API keys/secrets are encrypted before durable storage and API responses expose only a masked API-key identifier. The raw secret is decrypted only inside a live adapter after all LIVE gates have passed.

Before any future live activation, an authorized administrator must rotate/verify credentials, confirm the exchange account has no withdrawal permission, validate account and market-data access, record a successful verification time, and retain the audit record. The current BingX path is intentionally gated and not certified for real order submission.
