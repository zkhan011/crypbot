"""Validate and render the machine-readable BingX endpoint registry."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "bingx-endpoints.yaml"
COVERAGE = ROOT / "docs" / "bingx-api-coverage.md"

REQUIRED_FIELDS = {
    "operation",
    "product",
    "module",
    "method",
    "path",
    "authentication",
    "required_parameters",
    "optional_parameters",
    "request_schema",
    "response_schema",
    "rate_limit_scope",
    "rate_limit_value",
    "idempotency",
    "environments",
    "source_reference",
    "implementation_status",
    "test_status",
}


def load_registry() -> dict[str, object]:
    value = json.loads(REGISTRY.read_text())
    if not isinstance(value, dict):
        raise ValueError("registry root must be an object")
    return value


def validate() -> list[str]:
    payload = load_registry()
    errors: list[str] = []
    seen: set[str] = set()
    endpoints = payload.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        return ["registry contains no endpoints"]
    for index, endpoint in enumerate(endpoints, start=1):
        if not isinstance(endpoint, dict):
            errors.append(f"endpoint {index} is not an object")
            continue
        missing = REQUIRED_FIELDS - endpoint.keys()
        if missing:
            errors.append(f"endpoint {index} missing: {', '.join(sorted(missing))}")
        operation = str(endpoint.get("operation", ""))
        if operation in seen:
            errors.append(f"duplicate operation: {operation}")
        seen.add(operation)
        if endpoint.get("implementation_status") == "BLOCKED_SPEC" and endpoint.get("rate_limit_value") != "unknown":
            errors.append(f"{operation}: blocked specification must not invent a rate limit")
        if not str(endpoint.get("path", "")).startswith("/openApi/"):
            errors.append(f"{operation}: invalid endpoint path")
    return errors


def render() -> str:
    payload = load_registry()
    endpoints = payload["endpoints"]
    assert isinstance(endpoints, list)
    status_counts = Counter(str(item["implementation_status"]) for item in endpoints)
    lines = [
        "# BingX API coverage ledger",
        "",
        f"Registry schema: `{payload['schema_version']}`<br>",
        f"Contract source: `{payload['authoritative_source']}`<br>",
        f"Recorded: `{payload['retrieved_at']}`",
        "",
        "This document is generated from `config/bingx-endpoints.yaml`. Run `python scripts/validate_bingx_registry.py --write` after registry changes. Rate-limit values are configurable application safety caps because the supplied contract does not provide exchange numeric limits. LIVE remains disabled.",
        "",
        "## Totals",
        "",
        f"Total contracts: **{len(endpoints)}**. "
        + ", ".join(f"`{key}`: **{value}**" for key, value in sorted(status_counts.items()))
        + ".",
        "",
        "## Endpoint matrix",
        "",
        "| Product | Module | Operation | Method | Path | Auth | Required | Optional | Rate scope/value | Status | Tests |",
        "|---|---|---|---:|---|---|---|---|---|---|---|",
    ]
    for item in endpoints:
        required = ", ".join(f"`{value}`" for value in item["required_parameters"]) or "—"
        optional = ", ".join(f"`{value}`" for value in item["optional_parameters"]) or "—"
        lines.append(
            f"| {item['product']} | {item['module']} | `{item['operation']}` | {item['method']} | `{item['path']}` | {item['authentication']} | {required} | {optional} | {item['rate_limit_scope']} / {item['rate_limit_value']} | {item['implementation_status']} | {item['test_status']} |"
        )
    lines += [
        "",
        "## Deliberately disabled operations",
        "",
        "Cancel/replace and optional official copy-trading operations remain `DISABLED_SCHEMA` because the supplied contract gives endpoint paths but not complete request/response fields. Their methods fail closed rather than inventing fields. Withdrawals are prohibited and are not present in the registry or code.",
        "",
        "## Remaining controlled-demo gates",
        "",
        "- Add sanitized parser fixtures for entries marked `UNIT_PENDING`.",
        "- Configure and review application rate caps for each deployment; supplied contracts contain no numeric exchange limits.",
        "- Configure public/private WebSocket URLs and subscription payloads; unverified private subscriptions remain disabled.",
        "- Apply migration `0004_bingx_execution_records`, complete startup reconciliation, and run the non-trading certification report.",
        "- Enable the test-order endpoint only with an explicit DEMO flag. Automated tests never contact BingX.",
        "- Perform controlled BingX DEMO verification before considering any order mutation.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    failures = validate()
    if failures:
        raise SystemExit("\n".join(failures))
    rendered = render()
    if args.write:
        COVERAGE.write_text(rendered)
    elif not COVERAGE.exists() or COVERAGE.read_text() != rendered:
        raise SystemExit("BingX coverage ledger is stale; run with --write")
    print("BingX endpoint registry and coverage ledger are consistent.")
