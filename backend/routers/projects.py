from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime
import json

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.project import Project
from backend.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, CompetitorDetail
from backend.schemas.report import ReportMetadata
from backend.services import report_service

from sqlalchemy.orm import selectinload

router = APIRouter()

MAX_COMPETITORS = 5


def _serialize_competitor_details(competitors: Optional[List[CompetitorDetail]]) -> Optional[str]:
    """Validates (max 5) and serializes competitor details to a JSON string for storage.
    None or an empty list both mean "skip" and are stored as None."""
    if not competitors:
        return None
    if len(competitors) > MAX_COMPETITORS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_COMPETITORS} competitors are allowed")
    return json.dumps([c.model_dump() for c in competitors])


@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    competitor_details_json = _serialize_competitor_details(project.competitor_details)

    # Reuse an existing unused project (0 messages) for this brand if available
    existing_result = await db.execute(
        select(Project)
        .options(selectinload(Project.messages))
        .where(Project.user_id == current_user.id, Project.brand_config_id == project.brand_config_id)
        .order_by(Project.created_at.desc())
    )
    existing_projects = existing_result.scalars().all()
    for p in existing_projects:
        if not p.messages:
            p.title = project.title
            p.agent_type = project.agent_type
            if project.llm_provider:
                p.llm_provider = project.llm_provider
            p.competitor_details = competitor_details_json
            p.created_at = datetime.utcnow()
            await db.commit()
            res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == p.id))
            return res.scalars().first()

    # Otherwise create a new chat project for this brand
    project_data = project.model_dump(exclude={"competitor_details"})
    db_project = Project(**project_data, competitor_details=competitor_details_json, user_id=current_user.id)
    db.add(db_project)
    await db.commit()
    res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == db_project.id))
    return res.scalars().first()

@router.get("/", response_model=List[ProjectResponse])
async def get_projects(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.messages))
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    all_projects = result.scalars().all()
    return all_projects

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.messages))
        .where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, project_update: ProjectUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = project_update.model_dump(exclude_unset=True)
    if "competitor_details" in update_data:
        update_data["competitor_details"] = _serialize_competitor_details(project_update.competitor_details)
    for key, value in update_data.items():
        setattr(project, key, value)

    await db.commit()
    res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == project_id))
    return res.scalars().first()

@router.get("/{project_id}/reports", response_model=List[ReportMetadata])
async def get_project_reports(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return await report_service.list_reports(db, project_id, current_user.id)

@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import delete
    from backend.models.message import Message

    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. Delete all messages associated with this project from database
    await db.execute(delete(Message).where(Message.project_id == project_id))

    # 2. Delete the project record itself from database
    await db.delete(project)
    await db.commit()

    return {"detail": "Chat project and messages deleted from database"}
