"""Validate the machine-readable BingX registry without third-party packages."""

from __future__ import annotations

import json
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


def validate() -> list[str]:
    payload = json.loads(REGISTRY.read_text())
    coverage = COVERAGE.read_text()
    errors: list[str] = []
    seen: set[str] = set()
    for index, endpoint in enumerate(payload.get("endpoints", []), start=1):
        missing = REQUIRED_FIELDS - endpoint.keys()
        if missing:
            errors.append(f"endpoint {index} missing: {', '.join(sorted(missing))}")
        operation = endpoint.get("operation", "")
        if operation in seen:
            errors.append(f"duplicate operation: {operation}")
        seen.add(operation)
        if endpoint.get("implementation_status") == "BLOCKED_SPEC":
            if endpoint.get("rate_limit_value") != "unknown":
                errors.append(f"{operation}: blocked specification must not invent a rate limit")
            if not str(endpoint.get("source_reference", "")).startswith("BLOCKED_SPEC"):
                errors.append(f"{operation}: blocked specification requires a blocker source reference")
        path = endpoint.get("path", "")
        if path and path not in coverage:
            errors.append(f"{operation}: path missing from coverage ledger")
    if not seen:
        errors.append("registry contains no endpoints")
    return errors


if __name__ == "__main__":
    failures = validate()
    if failures:
        raise SystemExit("\n".join(failures))
    print("BingX endpoint registry and coverage ledger are consistent.")
