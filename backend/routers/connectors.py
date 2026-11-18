from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.schemas.connector import ConnectorCredentialCreate, ConnectorCredentialResponse
from backend.services import connector_service

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


# ── POST /api/connectors — save/update a credential ──────────────────────────
@router.post("", response_model=ConnectorCredentialResponse)
async def save_credential(
    body: ConnectorCredentialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await connector_service.upsert_credential(
        db,
        user_id=current_user.id,
        connector_id=body.connector_id,
        connector_type=body.connector_type,
        credentials=body.credentials,
    )
    return result


# ── GET /api/connectors — list the current user's connected connectors ──────
@router.get("", response_model=List[ConnectorCredentialResponse])
async def get_connectors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await connector_service.list_credentials(db, user_id=current_user.id)


# ── DELETE /api/connectors/{connector_id} — remove a credential ─────────────
@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_credential(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await connector_service.delete_credential(db, user_id=current_user.id, connector_id=connector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector credential not found")
