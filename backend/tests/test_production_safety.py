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
    with pytest.raises(RuntimeError, match="LIVE mode requires CRYPBOT_LIVE_TRADING_ENV_ENABLED=true"):
        Settings(execution_mode="LIVE", live_trading_env_enabled=False).validate_startup_security()
    with pytest.raises(RuntimeError, match="encryption master key"):
        Settings(execution_mode="LIVE", live_trading_env_enabled=True).validate_startup_security()
