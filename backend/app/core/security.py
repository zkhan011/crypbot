import base64, json, re
from dataclasses import dataclass
from typing import Any
from argon2 import PasswordHasher
from cryptography.fernet import Fernet, InvalidToken

SECRET_PATTERNS = [re.compile(p, re.I) for p in ["api[_-]?secret", "signature", "authorization", "token", "password"]]


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***REDACTED***" if any(p.search(k) for p in SECRET_PATTERNS) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _ph.verify(hashed, password)


@dataclass(frozen=True)
class EncryptedPayload:
    key_id: str
    ciphertext: str


class CredentialCipher:
    def __init__(self, master_key: str):
        if not master_key:
            master_key = "dev-master-key"
        key = base64.urlsafe_b64encode(master_key.encode().ljust(32, b"0")[:32])
        self._fernet = Fernet(key)
        self.key_id = "local-env-v1"

    def encrypt_json(self, payload: dict[str, str]) -> EncryptedPayload:
        token = self._fernet.encrypt(json.dumps(payload, sort_keys=True).encode()).decode()
        return EncryptedPayload(self.key_id, token)

    def decrypt_json(self, encrypted: EncryptedPayload) -> dict[str, str]:
        try:
            return json.loads(self._fernet.decrypt(encrypted.ciphertext.encode()))
        except InvalidToken as exc:
            raise ValueError("credential decryption failed") from exc

    @staticmethod
    def mask_key(key: str) -> str:
        return f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "***"
