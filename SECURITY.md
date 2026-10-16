# Security status and operating rules

- Default mode is MOCK. The live adapter refuses construction unless the explicit environment gate is enabled.
- API keys and secrets must be encrypted before persistence; API responses and logs must only expose masked values. Withdrawal permission is never required or permitted.
- Local demo accounts use Argon2 password hashes, opaque expiring sessions, login failure tracking, and role checks in backend control-plane methods.
- Mock notifications are previews only. No Telegram or email is sent unless a future live provider is deliberately configured.

This release is not certified for customer credentials or real funds. Complete the controls listed in `FEATURE_CHECKLIST.md` before a production deployment.

## Runtime credential handling

Do not paste live exchange API keys into source files, documentation, issue comments, PR descriptions, logs, or test fixtures. Live credentials must be rotated if they were shared in chat or another non-secret channel. Use the encrypted exchange-credential workflow at runtime; API responses must return only masked identifiers and verification metadata. CI runs `python scripts/check_no_secrets.py` to block likely committed secrets, but this scanner is a defense-in-depth control and not a substitute for secret-manager storage, least-privilege exchange permissions, IP whitelisting, and manual security review.
