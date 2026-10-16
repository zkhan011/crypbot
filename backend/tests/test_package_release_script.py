import importlib.util
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "package_release.py"
SPEC = importlib.util.spec_from_file_location("package_release", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def committed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Release Test")
    (repo / "README.md").write_text("release fixture\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-qm", "fixture")
    return repo


def test_package_contains_committed_tree_and_checksum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = committed_repo(tmp_path)
    monkeypatch.chdir(repo)
    archive, checksum, metadata = MODULE.package(tmp_path / "out")
    assert archive.is_file() and checksum.is_file() and metadata.is_file()
    assert checksum.read_text().split()[0] == MODULE.sha256(archive)
    listing = subprocess.run(["tar", "-tzf", archive], check=True, capture_output=True, text=True).stdout
    assert listing.endswith("/README.md\n")
    assert '"release_class": "LIVE_CANDIDATE"' in metadata.read_text()
    assert '"real_money_certified": false' in metadata.read_text()


def test_package_refuses_uncommitted_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = committed_repo(tmp_path)
    (repo / "untracked-secret.env").write_text("not packaged")
    monkeypatch.chdir(repo)
    with pytest.raises(RuntimeError, match="dirty working tree"):
        MODULE.package(tmp_path / "out")


def test_readiness_report_can_mark_technical_readiness_but_not_external_certification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = committed_repo(tmp_path)
    monkeypatch.chdir(repo)
    report = tmp_path / "readiness.json"
    report.write_text('{"production_readiness":{"state":"LIVE_READY","opening_orders_allowed":true,"checks":[{"id":"all","passed":true}]}}')
    _, _, metadata = MODULE.package(tmp_path / "out", readiness_report=report)
    contents = metadata.read_text()
    assert '"release_class": "TECHNICALLY_LIVE_READY"' in contents
    assert '"external_certification": "NOT_ATTESTED"' in contents
    assert '"real_money_certified": false' in contents
