#!/usr/bin/env python3
"""Fail CI when likely raw credentials are committed.

This is intentionally conservative for source files. Real exchange credentials must
only be supplied through a secret manager or protected runtime environment and then
stored via the encrypted credential service; they must never be checked into Git.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path

ALLOWLIST_PATHS = {
    ".env.example",
    "production.env.example",
}
ALLOWLIST_EXTENSIONS = {".md"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_\-+/=]{48,}")
ASSIGNMENT_RE = re.compile(r"(?i)(api[_-]?key|api[_-]?secret|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-+/=]{12,})")
PLACEHOLDER_WORDS = {"replace", "example", "invalid", "development", "local", "placeholder", "change", "dev", "secure"}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], text=True)
    return [Path(line) for line in output.splitlines() if line]


def entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    return -sum((count / len(value)) * math.log2(count / len(value)) for count in counts.values())


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def scan_file(path: Path) -> list[str]:
    if str(path) in ALLOWLIST_PATHS or path.suffix in ALLOWLIST_EXTENSIONS:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in ASSIGNMENT_RE.finditer(line):
            value = match.group(2)
            if not is_placeholder(value):
                findings.append(f"{path}:{line_no}: suspicious secret assignment")
        for match in TOKEN_RE.finditer(line):
            value = match.group(0)
            if entropy(value) >= 4.5 and not is_placeholder(value):
                findings.append(f"{path}:{line_no}: high-entropy token-like value")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        findings.extend(scan_file(path))
    if findings:
        print("Potential committed secrets detected:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        print("Store credentials only via encrypted runtime credential APIs.", file=sys.stderr)
        return 1
    print("No committed secret patterns detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
