"""
Public Router
===============
Unauthenticated endpoints only. Nothing here depends on get_current_user —
every route is reachable by anyone with the right token/id, by design.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.report import PublicReport
from backend.services import share_service

router = APIRouter()

@router.get("/reports/{token}", response_model=PublicReport)
async def get_public_report(token: str, db: AsyncSession = Depends(get_db)):
    report = await share_service.get_shared_report(db, token)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
