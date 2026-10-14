import importlib.util
from pathlib import Path
import stat
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "configure_bingx_live.py"
SPEC = importlib.util.spec_from_file_location("configure_bingx_live", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CONFIRMATION = MODULE.CONFIRMATION
REPOSITORY = MODULE.REPOSITORY
_outside_repository = MODULE._outside_repository
write_candidate = MODULE.write_candidate


def test_refuses_to_write_credentials_inside_repository() -> None:
    with pytest.raises(ValueError, match="inside the repository"):
        _outside_repository(REPOSITORY / ".live.env")


def test_writes_protected_candidate_without_echoing_secrets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "live.env"
    public_answers = iter([CONFIRMATION, "admin@example.test"])
    secrets = iter(["jwt value", "master-value", "postgres-value", "redis-value", "api-key-value", "api-secret-value"])
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("builtins.input", side_effect=lambda _: next(public_answers)),
        patch("getpass.getpass", side_effect=lambda _: next(secrets)),
    ):
        write_candidate(output)
    contents = output.read_text()
    assert "BINGX_API_KEY=api-key-value" in contents
    assert "BINGX_API_SECRET=api-secret-value" in contents
    assert "CRYPBOT_JWT_SECRET='jwt value'" in contents
    assert "BINGX_LIVE_TRADING_ENABLED=true" in contents
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    terminal = capsys.readouterr().out
    assert "api-key-value" not in terminal
    assert "api-secret-value" not in terminal


def test_refuses_overwriting_existing_candidate(tmp_path: Path) -> None:
    output = tmp_path / "live.env"
    output.write_text("existing")
    public_answers = iter([CONFIRMATION, "admin@example.test"])
    secrets = iter(["jwt", "master", "postgres", "redis", "key", "secret"])
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("builtins.input", side_effect=lambda _: next(public_answers)),
        patch("getpass.getpass", side_effect=lambda _: next(secrets)),
        pytest.raises(FileExistsError),
    ):
        write_candidate(output)
    assert output.read_text() == "existing"
