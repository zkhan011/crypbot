"""Durable-storage primitives that preserve secret and audit safety boundaries.

Repositories must persist only the encrypted credential payload and masked API
key.  The hash chain is deliberately deterministic and serializes audit data
before calculating the next link, making accidental mutation detectable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.security import CredentialCipher, EncryptedPayload, redact


GENESIS_HASH = "0" * 64


def canonical_audit_payload(event: dict[str, Any]) -> bytes:
    return json.dumps(redact(event), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def chain_hash(previous_hash: str, event: dict[str, Any]) -> str:
    return hashlib.sha256(previous_hash.encode("ascii") + canonical_audit_payload(event)).hexdigest()


@dataclass(frozen=True)
class AuditChainEntry:
    sequence: int
    previous_hash: str
    entry_hash: str
    event: dict[str, Any]


class AuditHashChain:
    def __init__(self) -> None:
        self._entries: list[AuditChainEntry] = []

    def append(self, event: dict[str, Any]) -> AuditChainEntry:
        safe_event = redact(event)
        previous_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        entry = AuditChainEntry(len(self._entries) + 1, previous_hash, chain_hash(previous_hash, safe_event), safe_event)
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        previous_hash = GENESIS_HASH
        for index, entry in enumerate(self._entries, start=1):
            if entry.sequence != index or entry.previous_hash != previous_hash:
                return False
            if entry.entry_hash != chain_hash(previous_hash, entry.event):
                return False
            previous_hash = entry.entry_hash
        return True


@dataclass(frozen=True)
class StoredCredential:
    tenant_id: str
    exchange: str
    api_key_masked: str
    payload: EncryptedPayload
    verified_at: datetime | None
    withdrawal_permission_verified: bool | None


class ExchangeCredentialService:
    """Encryption/masking facade; verification must run through a live adapter."""

    def __init__(self, cipher: CredentialCipher) -> None:
        self._cipher = cipher

    def store(self, tenant_id: str, exchange: str, api_key: str, api_secret: str) -> StoredCredential:
        encrypted = self._cipher.encrypt_json({"api_key": api_key, "api_secret": api_secret})
        return StoredCredential(tenant_id, exchange, self._cipher.mask_key(api_key), encrypted, None, None)

    def public(self, stored: StoredCredential) -> dict[str, str | bool | None]:
        return {
            "tenant_id": stored.tenant_id,
            "exchange": stored.exchange,
            "api_key_masked": stored.api_key_masked,
            "verified_at": stored.verified_at.isoformat() if stored.verified_at else None,
            "withdrawal_permission_verified": stored.withdrawal_permission_verified,
        }

    def decrypt_for_adapter(self, stored: StoredCredential) -> dict[str, str]:
        return self._cipher.decrypt_json(stored.payload)


def utc_now() -> datetime:
    return datetime.now(UTC)
