#!/usr/bin/env python3
"""Build a reproducible source package from the committed Git tree."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _technical_readiness(report: Path | None) -> tuple[str, list[str]]:
    if report is None:
        return "LIVE_CANDIDATE", ["production readiness report was not supplied"]
    payload = json.loads(report.read_text(encoding="utf-8"))
    readiness = payload.get("production_readiness", payload)
    checks = readiness.get("checks", [])
    failed = [
        str(check.get("id", "unknown"))
        for check in checks
        if check.get("passed") is not True
    ]
    if (
        readiness.get("state") != "LIVE_READY"
        or readiness.get("opening_orders_allowed") is not True
        or failed
    ):
        return "LIVE_CANDIDATE", failed or ["server did not report LIVE_READY"]
    return "TECHNICALLY_LIVE_READY", []


def package(
    output_dir: Path, *, allow_dirty: bool = False, readiness_report: Path | None = None
) -> tuple[Path, Path, Path]:
    if not allow_dirty and (_git("status", "--porcelain")):
        raise RuntimeError("refusing to package a dirty working tree")
    commit = _git("rev-parse", "--short=12", "HEAD")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"crypbot-{commit}.tar.gz"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    metadata = output_dir / f"crypbot-{commit}.release.json"
    subprocess.run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            f"--prefix=crypbot-{commit}/",
            "-o",
            str(archive),
            "HEAD",
        ],
        check=True,
    )
    checksum.write_text(f"{sha256(archive)}  {archive.name}\n", encoding="ascii")
    release_class, blockers = _technical_readiness(readiness_report)
    metadata.write_text(
        json.dumps(
            {
                "commit": commit,
                "archive": archive.name,
                "sha256": sha256(archive),
                "release_class": release_class,
                "technical_blockers": blockers,
                "external_certification": "NOT_ATTESTED",
                "real_money_certified": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return archive, checksum, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist-release"))
    parser.add_argument(
        "--readiness-report", type=Path, help="saved /api/v1/bingx/readiness JSON"
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="package HEAD while ignoring uncommitted files",
    )
    args = parser.parse_args()
    try:
        archive, checksum, metadata = package(
            args.output_dir,
            allow_dirty=args.allow_dirty,
            readiness_report=args.readiness_report,
        )
    except (
        RuntimeError,
        subprocess.CalledProcessError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        parser.exit(2, f"package failed: {exc}\n")
    print(f"archive={archive}")
    print(f"checksum={checksum}")
    print(f"metadata={metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
