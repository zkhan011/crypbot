# Penetration-test checklist

- Verify authentication, session fixation resistance, refresh-token reuse detection, MFA, password reset, rate limiting, and account lockout.
- Attempt tenant-crossing object IDs across users, bots, reports, drafts, credentials, audit records, and notification logs.
- Search API/log/export/browser state for API keys, secrets, tokens, passwords, and decrypted payloads.
- Test live-trading gates, strategy approval/mock-test requirements, risk rejection, emergency stop, and exchange-outage failure closure.
- Verify audit hash-chain persistence/tamper detection, Docker permissions, TLS headers, dependency vulnerabilities, backups, restoration, and incident response.
