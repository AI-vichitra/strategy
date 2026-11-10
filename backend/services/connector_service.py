"""
Connector Service
==================
DB logic for per-user connector credentials (ConnectorCredential table).
Credentials are stored as an encrypted JSON blob (see encryption_service.py).
The table has no unique constraint on (user_id, connector_id), so upsert
semantics are implemented here in code.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.models.connector import ConnectorCredential
from backend.services import encryption_service

logger = logging.getLogger(__name__)


def _public_fields(row: ConnectorCredential) -> Dict[str, Any]:
    return {
        "connector_id": row.connector_id,
        "connector_type": row.connector_type,
        "status": row.status,
        "connected_at": row.connected_at,
    }


async def _get_row(db: AsyncSession, user_id: str, connector_id: str) -> Optional[ConnectorCredential]:
    result = await db.execute(
        select(ConnectorCredential).where(
            ConnectorCredential.user_id == user_id,
            func.lower(ConnectorCredential.connector_id) == connector_id.lower(),
        )
    )
    return result.scalars().first()


async def upsert_credential(
    db: AsyncSession,
    user_id: str,
    connector_id: str,
    connector_type: str,
    credentials: Dict[str, Any],
) -> Dict[str, Any]:
    """Encrypts and stores credentials, inserting or updating the row for (user_id, connector_id)."""
    encrypted = encryption_service.encrypt(json.dumps(credentials))

    row = await _get_row(db, user_id, connector_id)
    if row is not None:
        row.encrypted_credentials = encrypted
        row.connector_type = connector_type
        row.status = "connected"
        row.connected_at = datetime.utcnow()
    else:
        row = ConnectorCredential(
            user_id=user_id,
            connector_id=connector_id,
            connector_type=connector_type,
            encrypted_credentials=encrypted,
            status="connected",
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return _public_fields(row)


async def list_credentials(db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
    """Returns non-secret fields for every connector credential belonging to the user."""
    result = await db.execute(
        select(ConnectorCredential).where(ConnectorCredential.user_id == user_id)
    )
    return [_public_fields(row) for row in result.scalars().all()]


async def delete_credential(db: AsyncSession, user_id: str, connector_id: str) -> bool:
    """Deletes the row for (user_id, connector_id), case-insensitive. Returns False if not found."""
    row = await _get_row(db, user_id, connector_id)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def get_credentials(db: AsyncSession, user_id: str, connector_id: str) -> Optional[Dict[str, Any]]:
    """
    Internal use only — fetches and decrypts the stored credentials dict.
    Never expose this via an API route.
    """
    row = await _get_row(db, user_id, connector_id)
    if row is None:
        return None
    decrypted = encryption_service.decrypt(row.encrypted_credentials)
    return json.loads(decrypted)


async def get_api_key(
    db: AsyncSession,
    user_id: str,
    connector_id: str,
    env_fallback: Optional[str] = None,
) -> Optional[str]:
    """
    Returns the user's stored "apiKey" for connector_id if present; otherwise falls
    back to os.environ[env_fallback] when given; otherwise None.
    """
    import os

    credentials = await get_credentials(db, user_id, connector_id)
    if credentials and credentials.get("apiKey"):
        return credentials["apiKey"]
    if env_fallback:
        return os.environ.get(env_fallback) or None
    return None
