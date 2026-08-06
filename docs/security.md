# Security

- Plaintext exchange secrets are never stored; local development uses envelope encryption via a master key abstraction.
- Secret-like fields are redacted before logging or API exposure.
- Startup validation rejects insecure defaults in staging/production and prevents accidental LIVE mode.
- Argon2id password hashing is used for credentials.
- Tenant-owned records include `organization_id` in the schema.
- LIVE trading is blocked by default and BingX live order submission is intentionally gated pending certification.

Remaining before production: external KMS/HSM integration, threat modeling, independent code review, SAST/DAST, penetration test, compliance review, withdrawal-permission verification against exchange APIs, and incident-response drills.
