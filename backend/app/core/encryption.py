"""
Encryption utilities for securing user API keys at rest.

Uses Fernet symmetric encryption so API keys are never stored in plaintext.
"""

from __future__ import annotations

from app.config import settings


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return the ciphertext as a string."""
    return settings.fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return the plaintext."""
    return settings.fernet.decrypt(ciphertext.encode()).decode()


def mask_key(key: str) -> str:
    """Show only the first 4 and last 4 characters of an API key."""
    if len(key) <= 10:
        return key[:2] + "•" * (len(key) - 2)
    return key[:4] + "•" * (len(key) - 8) + key[-4:]
