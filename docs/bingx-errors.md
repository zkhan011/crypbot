# BingX error handling reference

Only HTTP-level categories are currently verified by implementation. Exchange-specific numeric code mappings remain `BLOCKED_SPEC` and must not be guessed.

| Type | Meaning | Safe response |
|---|---|---|
| `BingXAuthenticationError` | HTTP 401 | Disable account, verify secret injection and key status without logging values. |
| `BingXPermissionError` | HTTP 403 | Keep strategy paused; verify trading/read permission and absence of withdrawal permission. |
| `BingXRateLimitError` | HTTP 429 | Stop opening exposure, preserve verified emergency capacity, honor retry metadata after specification review. |
| `BingXMalformedResponseError` | Invalid JSON/envelope | Open circuit, reconcile through a separately healthy read path, retain sanitized correlation metadata. |
| `BingXLiveTradingDisabled` | One or more platform gates absent | Keep LIVE disabled; do not bypass the missing gate. |
| `UnverifiedRateLimitError` | Endpoint limit is unknown or local capacity exhausted | Opening action remains disabled; verified risk-reducing cancellation capacity may continue. |
| `CircuitOpenError` | Repeated network/exchange failures | Block exposure increases; reconcile before reset. Risk-reducing operations remain separately available where safe. |

The adapter never includes API keys, signatures, signed URLs, headers, cookies, account identifiers, or raw response bodies in normalized exceptions. Prompt-supplied mappings include `101206` insufficient balance; `101209`/`110287` position limit; `101211`/`110400`/`110402` invalid parameters or price; `101414` leverage; `101415`/`109417`/`109425` symbol restrictions; `101419` pending-order restriction; `109403` risk restriction; `109420`/`109421` missing position/order; `109429` invalid-request rate restriction; and `110406` stop-loss conflict. Unknown codes fall back to `BingXExchangeFailureError`.
