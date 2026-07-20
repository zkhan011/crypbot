"""SQLAlchemy integration tests; run against PostgreSQL in CI/customer staging.

SQLite is used only as an isolated test database and is never a production
runtime option.
"""

import pytest
from sqlalchemy import create_engine

from app.db.models import metadata
from app.db.repositories import (
    BotInstanceRepository,
    RepositoryNotFoundError,
    TenantRepository,
    VersionedSettingsRepository,
    live_start_allowed,
)


@pytest.fixture
def connection():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata.create_all(engine)
    with engine.begin() as conn:
        yield conn


def test_tenant_scoped_bot_and_versioned_settings_persist_for_new_repository(connection):
    tenants = TenantRepository(connection)
    tenant_a = tenants.create("Tenant A")
    tenant_b = tenants.create("Tenant B")
    bots = BotInstanceRepository(connection)
    bot = bots.create(tenant_a["id"], "Mock bot")
    assert BotInstanceRepository(connection).get(tenant_a["id"], bot["id"])["name"] == "Mock bot"
    with pytest.raises(RepositoryNotFoundError):
        bots.get(tenant_b["id"], bot["id"])
    settings = VersionedSettingsRepository(connection)
    first = settings.save(tenant_a["id"], "risk", {"max_leverage": "2"}, 0, "actor")
    second = settings.save(tenant_a["id"], "risk", {"max_leverage": "3"}, int(first["version"]), "actor")
    assert int(second["version"]) == 2


def test_live_start_requires_every_gate():
    allowed, code = live_start_allowed(None, True, True, True, True)
    assert not allowed and code == "CREDENTIAL_NOT_VERIFIED"
    allowed, code = live_start_allowed({"verification_status": "VERIFIED", "withdrawal_permission_verified": False}, True, True, True, True)
    assert allowed and code == "ALLOWED"
