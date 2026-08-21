from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(ValueError):
    pass


class SecretEncryption:
    def __init__(self, key: str) -> None:
        if not key:
            raise EncryptionError("Encryption key is required")
        try:
            self._fernet = Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise EncryptionError("Encryption key must be a valid Fernet key") from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise EncryptionError("Plaintext secret cannot be empty")
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise EncryptionError("Unable to decrypt secret") from exc

