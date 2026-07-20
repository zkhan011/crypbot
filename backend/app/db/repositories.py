"""Tenant-scoped SQLAlchemy Core repositories for the production runtime.

No method accepts an unscoped customer-owned identifier.  Service layers must
pass the caller's resolved tenant ID and decide whether a platform operator is
permitted to select a different tenant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, and_, insert, select, update

from app.db.models import audit_log_chain, bot_instances, exchange_credentials, system_settings, tenants
from app.services.durable_security import AuditHashChain, AuditChainEntry, StoredCredential


class RepositoryNotFoundError(LookupError):
    pass


class RepositoryConflictError(RuntimeError):
    pass


class TenantRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create(self, name: str) -> dict[str, Any]:
        tenant_id = str(uuid4())
        self.connection.execute(insert(tenants).values(id=tenant_id, name=name))
        return self.get(tenant_id)

    def get(self, tenant_id: str) -> dict[str, Any]:
        row = self.connection.execute(select(tenants).where(tenants.c.id == tenant_id)).mappings().one_or_none()
        if row is None:
            raise RepositoryNotFoundError("tenant not found")
        return dict(row)


class BotInstanceRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create(self, tenant_id: str, name: str, mode: str = "MOCK") -> dict[str, Any]:
        bot_id = str(uuid4())
        self.connection.execute(insert(bot_instances).values(id=bot_id, tenant_id=tenant_id, name=name, mode=mode, status="STOPPED"))
        return self.get(tenant_id, bot_id)

    def get(self, tenant_id: str, bot_id: str) -> dict[str, Any]:
        row = (
            self.connection.execute(select(bot_instances).where(and_(bot_instances.c.id == bot_id, bot_instances.c.tenant_id == tenant_id)))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RepositoryNotFoundError("bot not found")
        return dict(row)

    def list(self, tenant_id: str) -> list[dict[str, Any]]:
        return [
            dict(row) for row in self.connection.execute(select(bot_instances).where(bot_instances.c.tenant_id == tenant_id)).mappings()
        ]

    def set_status(self, tenant_id: str, bot_id: str, status: str) -> dict[str, Any]:
        result = self.connection.execute(
            update(bot_instances)
            .where(and_(bot_instances.c.id == bot_id, bot_instances.c.tenant_id == tenant_id))
            .values(status=status, updated_at=datetime.now(UTC))
        )
        if result.rowcount != 1:
            raise RepositoryNotFoundError("bot not found")
        return self.get(tenant_id, bot_id)


class VersionedSettingsRepository:
    def __init__(self, connection: Connection, table: Any = system_settings) -> None:
        self.connection = connection
        self.table = table

    def get(self, tenant_id: str, key: str) -> dict[str, Any]:
        where = (
            and_(self.table.c.tenant_id == tenant_id, self.table.c.key == key)
            if "key" in self.table.c
            else self.table.c.tenant_id == tenant_id
        )
        row = self.connection.execute(select(self.table).where(where)).mappings().one_or_none()
        if row is None:
            raise RepositoryNotFoundError("settings not found")
        return dict(row)

    def save(self, tenant_id: str, key: str, value: dict[str, Any], expected_version: int | None, actor_id: str) -> dict[str, Any]:
        existing = None
        try:
            existing = self.get(tenant_id, key)
        except RepositoryNotFoundError:
            pass
        if existing is None:
            if expected_version not in (None, 0):
                raise RepositoryConflictError("settings version conflict")
            self.connection.execute(
                insert(self.table).values(id=str(uuid4()), tenant_id=tenant_id, key=key, value=value, version=1, updated_by=actor_id)
            )
        else:
            if expected_version != int(existing["version"]):
                raise RepositoryConflictError("settings version conflict")
            self.connection.execute(
                update(self.table)
                .where(self.table.c.id == existing["id"])
                .values(value=value, version=int(existing["version"]) + 1, updated_by=actor_id, updated_at=datetime.now(UTC))
            )
        return self.get(tenant_id, key)


class AuditChainRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def append(self, tenant_id: str, event: dict[str, Any]) -> dict[str, Any]:
        rows = self.connection.execute(
            select(audit_log_chain).where(audit_log_chain.c.tenant_id == tenant_id).order_by(audit_log_chain.c.sequence)
        ).mappings()
        chain = AuditHashChain()
        for row in rows:
            chain._entries.append(AuditChainEntry(int(row["sequence"]), row["previous_hash"], row["entry_hash"], row["event"]))
        entry = chain.append(event)
        self.connection.execute(
            insert(audit_log_chain).values(
                id=str(uuid4()),
                tenant_id=tenant_id,
                sequence=entry.sequence,
                previous_hash=entry.previous_hash,
                entry_hash=entry.entry_hash,
                event=entry.event,
            )
        )
        return {"sequence": entry.sequence, "entry_hash": entry.entry_hash}

    def verify(self, tenant_id: str) -> bool:
        rows = self.connection.execute(
            select(audit_log_chain).where(audit_log_chain.c.tenant_id == tenant_id).order_by(audit_log_chain.c.sequence)
        ).mappings()
        chain = AuditHashChain()
        for row in rows:
            chain._entries.append(AuditChainEntry(int(row["sequence"]), row["previous_hash"], row["entry_hash"], row["event"]))
        return chain.verify()


class ExchangeCredentialRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def save(self, credential: StoredCredential) -> dict[str, Any]:
        credential_id = str(uuid4())
        self.connection.execute(
            insert(exchange_credentials).values(
                id=credential_id,
                tenant_id=credential.tenant_id,
                exchange=credential.exchange,
                api_key_masked=credential.api_key_masked,
                key_id=credential.payload.key_id,
                ciphertext=credential.payload.ciphertext,
                verification_status="PENDING",
            )
        )
        return self.get(credential.tenant_id, credential_id)

    def get(self, tenant_id: str, credential_id: str) -> dict[str, Any]:
        row = (
            self.connection.execute(
                select(exchange_credentials).where(
                    and_(exchange_credentials.c.id == credential_id, exchange_credentials.c.tenant_id == tenant_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RepositoryNotFoundError("credential not found")
        return dict(row)

    def mark_verified(self, tenant_id: str, credential_id: str, withdrawal_permission_verified: bool) -> dict[str, Any]:
        status = "VERIFIED" if withdrawal_permission_verified is False else "REJECTED_WITHDRAWAL_PERMISSION"
        self.connection.execute(
            update(exchange_credentials)
            .where(and_(exchange_credentials.c.id == credential_id, exchange_credentials.c.tenant_id == tenant_id))
            .values(
                verification_status=status,
                withdrawal_permission_verified=withdrawal_permission_verified,
                verified_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        return self.get(tenant_id, credential_id)


def live_start_allowed(
    credential: dict[str, Any] | None, strategy_approved: bool, risk_configured: bool, final_confirmation: bool, environment_enabled: bool
) -> tuple[bool, str]:
    if not environment_enabled:
        return False, "LIVE_ENVIRONMENT_DISABLED"
    if credential is None or credential["verification_status"] != "VERIFIED" or credential["withdrawal_permission_verified"] is not False:
        return False, "CREDENTIAL_NOT_VERIFIED"
    if not strategy_approved:
        return False, "STRATEGY_NOT_APPROVED"
    if not risk_configured:
        return False, "RISK_NOT_CONFIGURED"
    if not final_confirmation:
        return False, "FINAL_CONFIRMATION_REQUIRED"
    return True, "ALLOWED"
