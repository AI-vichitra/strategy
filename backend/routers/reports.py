import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.project import Project
from backend.models.brand import BrandConfig
from backend.schemas.report import ReportDetail, ShareTokenResponse, ExportDocxRequest
from backend.services import report_service, export_service, share_service

router = APIRouter()

def _sanitize_filename_part(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", s or "").strip() or "Report"

async def _build_docx_response(db: AsyncSession, report, content_override: Optional[str]) -> Response:
    brand_result = await db.execute(
        select(BrandConfig.brand_name)
        .join(Project, Project.brand_config_id == BrandConfig.id)
        .where(Project.id == report.project_id)
    )
    brand_row = brand_result.first()
    brand_name = brand_row[0] if brand_row else None

    docx_bytes = await export_service.markdown_to_docx(
        db=db,
        report_id=report.id,
        content=report.content,
        title=report.title,
        brand_name=brand_name,
        agent_name=report.agent_type,
        content_override=content_override,
    )

    filename = f"{_sanitize_filename_part(brand_name or 'Brand')}_{_sanitize_filename_part(report.agent_type or 'Report')}.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = await report_service.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.get("/{report_id}/export/docx")
async def export_report_docx(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Always renders the report's raw, original content — unaffected by any section
    edits/hides/reorders — so existing frontend code and bookmarked links keep behaving
    exactly as before section-aware export (POST, below) was introduced."""
    report = await report_service.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return await _build_docx_response(db, report, content_override=report.content)

@router.post("/{report_id}/export/docx")
async def export_report_docx_with_content(
    report_id: str,
    req: ExportDocxRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Section-aware export. If `content` is given in the body (the section editor's
    finalized/reassembled markdown), it's rendered as-is. Otherwise, falls through to
    the report's parsed sections (visible, in order) when they exist, or its raw
    content when they don't — see export_service._resolve_export_content."""
    report = await report_service.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return await _build_docx_response(db, report, content_override=req.content)

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
