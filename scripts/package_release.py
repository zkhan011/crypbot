#!/usr/bin/env python3
"""Build a reproducible source package from the committed Git tree."""

from __future__ import annotations

import argparse
import hashlib
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


def package(output_dir: Path, *, allow_dirty: bool = False) -> tuple[Path, Path]:
    if not allow_dirty and (_git("status", "--porcelain")):
        raise RuntimeError("refusing to package a dirty working tree")
    commit = _git("rev-parse", "--short=12", "HEAD")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"crypbot-{commit}.tar.gz"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
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
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist-release"))
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="package HEAD while ignoring uncommitted files",
    )
    args = parser.parse_args()
    try:
        archive, checksum = package(args.output_dir, allow_dirty=args.allow_dirty)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"package failed: {exc}\n")
    print(f"archive={archive}")
    print(f"checksum={checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
