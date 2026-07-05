"""Encrypt/decrypt SimpleFIN access URLs at rest."""
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().fernet_key.strip()
    if not key:
        raise ValueError("FERNET_KEY is not configured")
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt stored credential — check FERNET_KEY") from exc
