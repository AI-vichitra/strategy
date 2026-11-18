from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.schemas.report_section import (
    ReportSectionResponse,
    SectionCreateRequest,
    SectionUpdateRequest,
    SectionReorderRequest,
)
from backend.services import report_service, section_service

router = APIRouter()


async def _get_owned_report(db: AsyncSession, report_id: str, user_id: str):
    report = await report_service.get_report(db, report_id, user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/sections", response_model=List[ReportSectionResponse])
async def get_sections(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_report(db, report_id, current_user.id)
    return await section_service.get_sections(db, report_id)


@router.post("/{report_id}/sections", response_model=ReportSectionResponse)
async def create_section(
    report_id: str,
    req: SectionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_report(db, report_id, current_user.id)
    return await section_service.create_section(
        db,
        report_id=report_id,
        after_order=req.after_order,
        title=req.title,
        content=req.content,
        section_type=req.section_type,
    )


@router.put("/{report_id}/sections/reorder", response_model=List[ReportSectionResponse])
async def reorder_sections(
    report_id: str,
    req: SectionReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_report(db, report_id, current_user.id)
    return await section_service.reorder_sections(db, report_id, req.section_ids)


@router.put("/{report_id}/sections/{section_id}", response_model=ReportSectionResponse)
async def update_section(
    report_id: str,
    section_id: int,
    req: SectionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_report(db, report_id, current_user.id)
    existing = await section_service.get_section(db, section_id)
    if not existing or existing.report_id != report_id:
        raise HTTPException(status_code=404, detail="Section not found")
    return await section_service.update_section(
        db,
        section_id=section_id,
        title=req.title,
        content=req.content,
        visible=req.visible,
    )


@router.delete("/{report_id}/sections/{section_id}")
async def delete_section(
    report_id: str,
    section_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_report(db, report_id, current_user.id)
    existing = await section_service.get_section(db, section_id)
    if not existing or existing.report_id != report_id:
        raise HTTPException(status_code=404, detail="Section not found")
    await section_service.delete_section(db, section_id)
    return {"detail": "Section deleted"}


@router.post("/{report_id}/sections/parse", response_model=List[ReportSectionResponse])
async def parse_report_sections(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await _get_owned_report(db, report_id, current_user.id)
    return await section_service.parse_report_into_sections(db, report_id, report.content)


@router.get("/{report_id}/sections/finalized")
async def get_finalized_content(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_report(db, report_id, current_user.id)
    content = await section_service.get_finalized_content(db, report_id)
    return {"content": content}
