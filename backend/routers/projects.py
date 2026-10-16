from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import datetime

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.project import Project
from backend.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

from sqlalchemy.orm import selectinload

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
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
            p.created_at = datetime.utcnow()
            await db.commit()
            res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == p.id))
            return res.scalars().first()

    # Otherwise create a new chat project for this brand
    db_project = Project(**project.model_dump(), user_id=current_user.id)
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
    for key, value in update_data.items():
        setattr(project, key, value)
        
    await db.commit()
    res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == project_id))
    return res.scalars().first()

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
