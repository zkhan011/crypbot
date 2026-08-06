"""SQLAlchemy integration tests; run against PostgreSQL in CI/customer staging.

SQLite is used only as an isolated test database and is never a production
runtime option.
"""

import pytest
from sqlalchemy import create_engine

from app.db.models import metadata
from app.db.repositories import (
    BotInstanceRepository,
    OrderIntentRepository,
    ReconciliationRunRepository,
    RepositoryNotFoundError,
    TenantRepository,
    SourceTradeEventRepository,
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


def test_source_dedup_order_intent_and_reconciliation_persist(connection):
    tenant = TenantRepository(connection).create("Execution tenant")
    bot = BotInstanceRepository(connection).create(tenant["id"], "Execution bot")
    source_events = SourceTradeEventRepository(connection)
    assert source_events.record_once(tenant["id"], "leader", "source-1", {"symbol": "BTC-USDT"})
    assert not source_events.record_once(tenant["id"], "leader", "source-1", {"symbol": "BTC-USDT"})

    intents = OrderIntentRepository(connection)
    intent = intents.create(
        tenant_id=tenant["id"],
        bot_id=bot["id"],
        account_id="account",
        environment="DEMO",
        product="USDT_M_PERPETUAL",
        strategy="COPY",
        source_event_id="source-1",
        client_order_id="deterministic-client-id",
        symbol="BTC-USDT",
        requested={"quantity": "0.001"},
    )
    assert OrderIntentRepository(connection).get(tenant["id"], intent["id"])["state"] == "PERSISTED"
    assert len(intents.unfinished(tenant["id"], "account")) == 1

    runs = ReconciliationRunRepository(connection)
    run = runs.start(tenant["id"], "account")
    completed = runs.complete(tenant["id"], run["id"], [{"category": "UNKNOWN_POSITION"}])
    assert completed["status"] == "MANUAL_REVIEW"
