#!/usr/bin/env python3
"""Create a protected LIVE-candidate environment file and inspect readiness.

This utility never calls an exchange and never submits an order. It cannot
bypass ProductionReadinessGate: generated flags only allow the API to start in
LIVE_PAUSED until every server-derived readiness check passes.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import shlex
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

CONFIRMATION = "PREPARE BINGX LIVE CANDIDATE"
REPOSITORY = Path(__file__).resolve().parents[1]


def _required(prompt: str, *, secret: bool = False) -> str:
    value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    if not value:
        raise ValueError(f"{prompt.rstrip(': ')} is required")
    if "\n" in value or "\r" in value:
        raise ValueError("environment values may not contain newlines")
    return value


def _outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(REPOSITORY)
    except ValueError:
        return resolved
    raise ValueError("refusing to write credentials inside the repository")


def write_candidate(path: Path) -> Path:
    output = _outside_repository(path)
    if not sys.stdin.isatty():
        raise ValueError(
            "interactive terminal required; secrets are never accepted as command-line arguments"
        )
    print(
        "This prepares configuration only. It does not certify readiness or place an order."
    )
    if input(f'Type "{CONFIRMATION}" to continue: ').strip() != CONFIRMATION:
        raise ValueError("confirmation did not match")
    values = {
        "CRYPBOT_ENVIRONMENT": "production",
        "CRYPBOT_EXECUTION_MODE": "LIVE",
        "CRYPBOT_ENABLE_LIVE_TRADING": "true",
        "CRYPBOT_SEED_DEMO_USERS": "false",
        "CRYPBOT_PRODUCTION_BOOTSTRAP_ADMIN_EMAIL": _required(
            "Bootstrap administrator email: "
        ),
        "CRYPBOT_JWT_SECRET": _required("JWT signing secret: ", secret=True),
        "CRYPBOT_CREDENTIAL_MASTER_KEY": _required(
            "Credential master key: ", secret=True
        ),
        "CRYPBOT_DATABASE_URL": _required("PostgreSQL URL: ", secret=True),
        "CRYPBOT_REDIS_URL": _required("Redis URL: ", secret=True),
        "CRYPBOT_BINGX_BASE_URL": "https://open-api.bingx.com",
        "CRYPBOT_BINGX_ENVIRONMENT": "LIVE",
        "CRYPBOT_BINGX_DRY_RUN": "false",
        "CRYPBOT_BINGX_LIVE_CONFIRMATION": "true",
        "CRYPBOT_BINGX_PUBLIC_MARKET_DATA_ENABLED": "true",
        "BINGX_API_KEY": _required("BingX API key: ", secret=True),
        "BINGX_API_SECRET": _required("BingX API secret: ", secret=True),
        "BINGX_ENVIRONMENT": "LIVE",
        "BINGX_BASE_URL": "https://open-api.bingx.com",
        "BINGX_RECV_WINDOW": "5000",
        "BINGX_DRY_RUN": "false",
        "BINGX_LIVE_TRADING_ENABLED": "true",
        "BINGX_LIVE_CONFIRMATION": "true",
    }
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(output, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for name, value in values.items():
                stream.write(f"{name}={shlex.quote(value)}\n")
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    print(f"Protected candidate written to {output} (mode 0600).")
    print(
        "Start the API, then run this script with --check-readiness. Do not trade unless state is LIVE_READY."
    )
    return output


def check_readiness(url: str) -> int:
    endpoint = url.rstrip("/") + "/api/v1/bingx/readiness"
    try:
        with urlopen(endpoint, timeout=10) as response:  # noqa: S310 - operator-supplied local deployment URL
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Readiness request failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    readiness = payload.get("production_readiness", {})
    checks = readiness.get("checks", [])
    print(
        json.dumps(
            {
                "state": readiness.get("state", "UNKNOWN"),
                "opening_orders_allowed": readiness.get(
                    "opening_orders_allowed", False
                ),
                "checks": checks,
            },
            indent=2,
        )
    )
    return (
        0
        if readiness.get("state") == "LIVE_READY"
        and readiness.get("opening_orders_allowed") is True
        else 3
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="new protected file outside the repository"
    )
    parser.add_argument(
        "--check-readiness",
        metavar="BASE_URL",
        help="inspect a running API; exits 3 unless LIVE_READY",
    )
    args = parser.parse_args()
    if bool(args.output) == bool(args.check_readiness):
        parser.error("choose exactly one of --output or --check-readiness")
    try:
        if args.output:
            write_candidate(args.output)
            return 0
        return check_readiness(args.check_readiness)
    except (OSError, ValueError) as exc:
        print(f"Configuration not written: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
