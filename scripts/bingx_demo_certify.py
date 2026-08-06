"""Generate a sanitized, non-trading BingX demo-readiness report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from validate_bingx_registry import validate

ROOT = Path(__file__).resolve().parents[1]


def build_report() -> dict[str, object]:
    registry_errors = validate()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": "DEMO",
        "dry_run": True,
        "live_trading_enabled": False,
        "registry_valid": not registry_errors,
        "registry_errors": registry_errors,
        "server_time": "IMPLEMENTED_NOT_CONTACTED",
        "authentication": "NOT_RUN",
        "balance": "NOT_RUN",
        "contracts": "NOT_RUN",
        "market_data": "NOT_RUN",
        "order_validation": "LOCAL_TEST_ONLY",
        "test_order": "IMPLEMENTED_BUT_DISABLED",
        "demo_order": "NOT_RUN",
        "final_reconciliation": "NOT_RUN",
        "live_order_placed": False,
        "certified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "bingx-demo-certification.json")
    parser.add_argument("--allow-demo-order", action="store_true")
    args = parser.parse_args()
    if args.allow_demo_order:
        raise SystemExit("Demo mutation is disabled until a separate demo URL and explicit certification approval are configured.")
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Sanitized non-trading report written to {args.output}")
    raise SystemExit(0 if report["registry_valid"] else 1)
