import asyncio
import json
import re
from typing import Optional, Tuple

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

async def _generate_report_docx_bytes(db: AsyncSession, report, content_override: Optional[str]) -> Tuple[bytes, str]:
    """Builds the branded docx for a report and returns (docx_bytes, title),
    where `title` is the sanitized "{brand}_{agent}" filename stem shared by
    every export format for this report (docx/pdf/pptx)."""
    brand_result = await db.execute(
        select(BrandConfig.brand_name, Project.brand_kit)
        .join(Project, Project.brand_config_id == BrandConfig.id)
        .where(Project.id == report.project_id)
    )
    brand_row = brand_result.first()
    brand_name = brand_row[0] if brand_row else None
    brand_kit_raw = brand_row[1] if brand_row else None
    brand_kit = json.loads(brand_kit_raw) if brand_kit_raw else None

    extracted_palette_raw = getattr(report, "extracted_palette", None)
    extracted_palette = json.loads(extracted_palette_raw) if extracted_palette_raw else None

    docx_bytes = await export_service.markdown_to_docx(
        db=db,
        report_id=report.id,
        content=report.content,
        title=report.title,
        brand_name=brand_name,
        agent_name=report.agent_type,
        content_override=content_override,
        brand_kit=brand_kit,
        extracted_palette=extracted_palette,
    )

    title = f"{_sanitize_filename_part(brand_name or 'Brand')}_{_sanitize_filename_part(report.agent_type or 'Report')}"
    return docx_bytes, title


async def _build_docx_response(db: AsyncSession, report, content_override: Optional[str]) -> Response:
    docx_bytes, title = await _generate_report_docx_bytes(db, report, content_override)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{title}.docx"'},
    )

async def _build_pptx_response(db: AsyncSession, report) -> Response:
    brand_result = await db.execute(
        select(BrandConfig.brand_name, Project.brand_kit)
        .join(Project, Project.brand_config_id == BrandConfig.id)
        .where(Project.id == report.project_id)
    )
    brand_row = brand_result.first()
    brand_name = brand_row[0] if brand_row else None
    brand_kit_raw = brand_row[1] if brand_row else None
    brand_kit = json.loads(brand_kit_raw) if brand_kit_raw else None

    extracted_palette_raw = getattr(report, "extracted_palette", None)
    extracted_palette = json.loads(extracted_palette_raw) if extracted_palette_raw else None

    try:
        from backend.services.pptx_service import generate_pptx
    except ModuleNotFoundError:
        from services.pptx_service import generate_pptx

    report_data = {
        "content": report.content,
        "title": report.title,
        "brand_name": brand_name,
        "agent_name": report.agent_type,
        "brand_kit": brand_kit,
        "extracted_palette": extracted_palette,
    }
    pptx_bytes = await generate_pptx(report_data)

    filename = f"{_sanitize_filename_part(brand_name or 'Brand')}_{_sanitize_filename_part(report.agent_type or 'Report')}.pptx"

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
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

@router.get("/{report_id}/export/pptx")
async def export_report_pptx(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Mirrors export_report_docx: renders the report's raw content as a branded
    PowerPoint deck via pptx_service.generate_pptx."""
    report = await report_service.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return await _build_pptx_response(db, report)

@router.get("/{report_id}/export/pdf")
async def export_report_pdf(report_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Renders the report's raw content as a branded docx (same theming as the
    DOCX export) and converts it to PDF via LibreOffice headless, so the PDF
    matches the DOCX exactly."""
    report = await report_service.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    docx_bytes, title = await _generate_report_docx_bytes(db, report, content_override=report.content)

    try:
        from backend.services.pdf_service import docx_bytes_to_pdf
    except ModuleNotFoundError:
        from services.pdf_service import docx_bytes_to_pdf

    try:
        pdf_bytes = await asyncio.to_thread(docx_bytes_to_pdf, docx_bytes)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"PDF conversion failed: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{title}.pdf"'},
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
