"""Fernet encryption helpers for storing OAuth tokens at rest."""

from cryptography.fernet import Fernet

from app.config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().fernet_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
