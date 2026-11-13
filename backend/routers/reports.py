import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.project import Project
from backend.models.brand import BrandConfig
from backend.schemas.report import ReportDetail, ShareTokenResponse
from backend.services import report_service, export_service, share_service

router = APIRouter()

def _sanitize_filename_part(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", s or "").strip() or "Report"

@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = await report_service.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.get("/{report_id}/export/docx")
async def export_report_docx(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = await report_service.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    brand_result = await db.execute(
        select(BrandConfig.brand_name)
        .join(Project, Project.brand_config_id == BrandConfig.id)
        .where(Project.id == report.project_id)
    )
    brand_row = brand_result.first()
    brand_name = brand_row[0] if brand_row else None

    docx_bytes = export_service.markdown_to_docx(
        content=report.content,
        title=report.title,
        brand_name=brand_name,
        agent_name=report.agent_type,
    )

    filename = f"{_sanitize_filename_part(brand_name or 'Brand')}_{_sanitize_filename_part(report.agent_type or 'Report')}.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.post("/{report_id}/share", response_model=ShareTokenResponse)
async def create_report_share(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    token = await share_service.create_share(db, report_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"token": token}

@router.delete("/{report_id}/share")
async def revoke_report_share(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ok = await share_service.revoke_share(db, report_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"detail": "Share revoked"}
