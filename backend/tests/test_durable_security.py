from app.core.security import CredentialCipher
from app.services.durable_security import AuditHashChain, ExchangeCredentialService


def test_audit_hash_chain_detects_mutation():
    chain = AuditHashChain()
    chain.append({"action": "LOGIN", "token": "must-not-enter-chain"})
    assert chain.verify()
    entry = chain._entries[0]  # Test tampering detection at the persistence boundary.
    entry.event["action"] = "MUTATED"
    assert not chain.verify()


def test_credential_service_masks_public_data_and_encrypts_secret():
    service = ExchangeCredentialService(CredentialCipher("test-master-key"))
    stored = service.store("tenant-a", "BINGX", "abcd1234efgh", "private-secret")
    public = service.public(stored)
    assert public["api_key_masked"] == "abcd...efgh"
    assert "private-secret" not in str(public)
    assert service.decrypt_for_adapter(stored)["api_secret"] == "private-secret"
