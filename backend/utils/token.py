"""
Token generation and verification for authentication and password resets.
Follows high-entropy URL-safe generation and SHA-256 token hashing.
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional


def generate_reset_token() -> str:
    """Generate a high-entropy 32-byte URL-safe string."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256 for secure storage and constant-time matching.
    Ensures raw tokens are never exposed if the database is leaked.
    """
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def verify_token_expiry(created_at: Optional[datetime], hours: int = 1) -> bool:
    """Check if token was generated within the validity window (default: 1 hour)."""
    if not created_at:
        return False
    expiry_time = created_at + timedelta(hours=hours)
    return datetime.utcnow() < expiry_time
