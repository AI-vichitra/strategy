"""
Encryption Service
===================
Fernet-based symmetric encryption for connector credentials at rest.
Key comes from CONNECTOR_ENCRYPTION_KEY (base64 urlsafe, generated with
Fernet.generate_key()). Never logs the key or any plaintext.
"""

import os
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key = os.environ.get("CONNECTOR_ENCRYPTION_KEY", "")
    if not key:
        logger.error("[encryption] CONNECTOR_ENCRYPTION_KEY is not set in environment")
        raise RuntimeError(
            "CONNECTOR_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it in backend/.env."
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as e:
        logger.error(f"[encryption] CONNECTOR_ENCRYPTION_KEY is invalid: {type(e).__name__}")
        raise RuntimeError(
            "CONNECTOR_ENCRYPTION_KEY is set but is not a valid Fernet key. "
            "Generate a new one with `Fernet.generate_key()` and update backend/.env."
        )


def encrypt(plaintext: str) -> bytes:
    """Encrypts a string, returning the Fernet token as bytes."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(blob: bytes) -> str:
    """Decrypts a Fernet token back into the original string."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(bytes(blob)).decode("utf-8")
    except InvalidToken:
        logger.error("[encryption] Failed to decrypt credential blob: invalid token")
        raise RuntimeError("Stored credential could not be decrypted — it may be corrupted or the encryption key changed.")
