"""Validate BingX runtime gates without printing credentials or contacting BingX."""

from __future__ import annotations

import json
import os


def flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, str(default)).lower()
    if raw not in {"true", "false", "1", "0"}:
        raise SystemExit(f"{name} must be true or false")
    return raw in {"true", "1"}


environment = os.environ.get("BINGX_ENVIRONMENT", "DEMO").upper()
if environment not in {"DEMO", "LIVE"}:
    raise SystemExit("BINGX_ENVIRONMENT must be DEMO or LIVE")
dry_run = flag("BINGX_DRY_RUN", True)
live_enabled = flag("BINGX_LIVE_TRADING_ENABLED", False)
confirmation = flag("BINGX_LIVE_CONFIRMATION", False)
base_url = os.environ.get("BINGX_BASE_URL", "").rstrip("/")
if base_url and not base_url.startswith("https://"):
    raise SystemExit("BINGX_BASE_URL must use HTTPS")
credentials_complete = bool(os.environ.get("BINGX_API_KEY")) and bool(os.environ.get("BINGX_API_SECRET"))
if environment == "LIVE" and (dry_run or not live_enabled or not confirmation or not credentials_complete):
    raise SystemExit("LIVE configuration is incomplete or disabled")
if os.environ.get("CI") and environment == "LIVE":
    raise SystemExit("automated environments may not select BingX LIVE")
print(
    json.dumps(
        {
            "environment": environment,
            "dry_run": dry_run,
            "live_trading_enabled": live_enabled,
            "live_confirmation": confirmation,
            "base_url_configured": bool(base_url),
            "credentials_complete": credentials_complete,
            "network_mutations_allowed": environment == "LIVE" and not dry_run and live_enabled and confirmation,
        },
        sort_keys=True,
    )
)
