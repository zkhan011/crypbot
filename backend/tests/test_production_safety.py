import pytest

from app.core.config import Settings


def test_production_rejects_demo_seed_and_missing_bootstrap_admin():
    with pytest.raises(RuntimeError, match="demo user seeding"):
        Settings(
            environment="production",
            jwt_secret="secure-secret",
            credential_master_key="secure-master-key",
            seed_demo_users=True,
            production_bootstrap_admin_email="admin@example.test",
        ).validate_startup_security()
    with pytest.raises(RuntimeError, match="bootstrap administrator"):
        Settings(
            environment="production",
            jwt_secret="secure-secret",
            credential_master_key="secure-master-key",
            seed_demo_users=False,
        ).validate_startup_security()


def test_live_requires_explicit_gate_and_encryption_key():
    with pytest.raises(RuntimeError, match="LIVE mode requires CRYPBOT_ENABLE_LIVE_TRADING=true"):
        Settings(execution_mode="LIVE", enable_live_trading=False).validate_startup_security()
    with pytest.raises(RuntimeError, match="encryption master key"):
        Settings(execution_mode="LIVE", enable_live_trading=True).validate_startup_security()


def test_live_requires_exchange_environment_dry_run_disable_and_confirmation():
    common = {
        "execution_mode": "LIVE",
        "enable_live_trading": True,
        "credential_master_key": "secure-master-key",
    }
    with pytest.raises(RuntimeError, match="BINGX_ENVIRONMENT=LIVE"):
        Settings(**common).validate_startup_security()
    with pytest.raises(RuntimeError, match="BINGX_DRY_RUN=false"):
        Settings(**common, bingx_environment="LIVE").validate_startup_security()
    with pytest.raises(RuntimeError, match="BINGX_LIVE_CONFIRMATION=true"):
        Settings(**common, bingx_environment="LIVE", bingx_dry_run=False).validate_startup_security()


def test_complete_live_flags_still_cannot_bypass_uncertified_runtime():
    with pytest.raises(RuntimeError, match="LIVE runtime is not certified"):
        Settings(
            execution_mode="LIVE",
            enable_live_trading=True,
            credential_master_key="secure-master-key",
            bingx_environment="LIVE",
            bingx_dry_run=False,
            bingx_live_confirmation=True,
        ).validate_startup_security()


def test_production_cannot_start_with_in_memory_control_plane():
    with pytest.raises(RuntimeError, match="production runtime is blocked"):
        Settings(
            environment="production",
            jwt_secret="secure-secret",
            credential_master_key="secure-master-key",
            seed_demo_users=False,
            production_bootstrap_admin_email="admin@example.test",
        ).validate_startup_security()
