"""
Encryption utilities for sensitive broker credentials.

Uses Fernet symmetric encryption from the ``cryptography`` package.  The
encryption key is read from ``settings.ENCRYPTION_KEY``; if that is not set,
a deterministic key is derived from ``settings.SECRET_KEY`` as a fallback.

Never log decrypted credential values; use :func:`mask_value` for display.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from config import settings


def _derive_key_from_secret(secret: str) -> bytes:
    """Derive a URL-safe base64 Fernet key from an arbitrary secret string.

    Fernet keys must be 32 raw bytes encoded as URL-safe base64 (44 chars).
    We SHA-256 the secret for stable entropy, take 32 bytes, then base64
    encode the result.
    """
    raw = hashlib.sha256(secret.encode("utf-8")).digest()[:32]
    return base64.urlsafe_b64encode(raw)


def get_fernet() -> Fernet:
    """Return a :class:`Fernet` instance.

    If ``settings.ENCRYPTION_KEY`` is set, it is used directly.  Otherwise a
    key is derived from ``settings.SECRET_KEY`` and a warning is logged.
    """
    key = settings.ENCRYPTION_KEY
    if key:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)

    logger.warning(
        "ENCRYPTION_KEY not set; deriving encryption key from SECRET_KEY. "
        "Set ENCRYPTION_KEY explicitly for stronger security."
    )
    derived = _derive_key_from_secret(settings.SECRET_KEY)
    return Fernet(derived)


def encrypt_value(value: Optional[str]) -> Optional[str]:
    """Encrypt a plaintext string, or return ``None``/empty as-is."""
    if not value:
        return value
    fernet = get_fernet()
    token = fernet.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(value: Optional[str]) -> Optional[str]:
    """Decrypt a Fernet token, or return ``None``/empty as-is.

    If decryption fails (e.g. wrong key or corrupt token), log an error and
    return ``None``.
    """
    if not value:
        return value
    fernet = get_fernet()
    try:
        plaintext = fernet.decrypt(value.encode("utf-8"))
        return plaintext.decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        logger.error("Failed to decrypt credential value: {}", exc)
        return None


def mask_value(value: Optional[str]) -> str:
    """Return a masked display string for a sensitive value.

    Format: ``****XXXX`` where ``XXXX`` is the last 4 characters.  Returns
    ``"Not set"`` when the value is empty.
    """
    if not value:
        return "Not set"
    if len(value) <= 4:
        return "****" + value
    return "****" + value[-4:]
