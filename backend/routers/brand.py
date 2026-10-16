from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from backend.database import async_session
from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.brand import BrandConfig
from backend.models.project import Project
from backend.schemas.brand import (
    BrandConfigCreate,
    BrandConfigResponse,
    BrandSearchRequest,
    BrandConfirmRequest,
    BrandStatusResponse,
)

router = APIRouter()


# ── GET /api/brands/ — list all brands for current user ─────────────────────
@router.get("/", response_model=List[BrandConfigResponse])
async def get_brands(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BrandConfig)
        .where(BrandConfig.user_id == current_user.id)
        .order_by(BrandConfig.created_at.desc())
    )
    return result.scalars().all()


# ── POST /api/brands/ — create brand directly (legacy / test) ───────────────
@router.post("/", response_model=BrandConfigResponse)
async def create_brand(
    brand: BrandConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_brand = BrandConfig(**brand.model_dump(), user_id=current_user.id)
    db.add(db_brand)
    await db.commit()
    await db.refresh(db_brand)
    return db_brand


# ── POST /api/brands/search-competitors ─────────────────────────────────────
@router.post("/search-competitors")
async def search_competitors(
    req: BrandSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Step 1 of brand setup: Runs Tavily to discover competitors.
    Returns candidate list for the frontend to display.
    Does NOT save anything to the DB yet.
    """
    from backend.services import tavily_service

    result = await __import__("asyncio").get_event_loop().run_in_executor(
        None,
        lambda: tavily_service.search_competitors(
            brand_name=req.brand_name,
            category=req.category,
            website_url=req.website_url,
            user_competitors=[c.model_dump() for c in (req.user_competitors or [])],
        ),
    )
    return result


# ── POST /api/brands/confirm ─────────────────────────────────────────────────
@router.post("/confirm", response_model=BrandConfigResponse)
async def confirm_brand(
    req: BrandConfirmRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2 of brand setup: Creates the BrandConfig + default Project in DB,
    then kicks off the full research pipeline as a BackgroundTask.
    Returns immediately so the user is not blocked.
    """
    import json
    from backend.services import pipeline_service

    # Create BrandConfig
    competitors_json = json.dumps([
        {"name": c.name, "url": c.website_url or ""}
        for c in req.selected_competitors
    ])
    db_brand = BrandConfig(
        user_id=current_user.id,
        brand_name=req.brand_name,
        website_url=req.website_url,
        category=req.category,
        brand_context=req.brand_context,
        competitors=competitors_json,
        brand_handle=req.brand_handle,
        pipeline_status="pending",
    )
    db.add(db_brand)
    await db.commit()
    await db.refresh(db_brand)

    # Create default Project
    db_project = Project(
        user_id=current_user.id,
        brand_config_id=db_brand.id,
        agent_type="StratAI",
        title=req.brand_name,
        description="Auto-created project",
    )
    db.add(db_project)
    await db.commit()

    # Launch pipeline in background — user is redirected immediately
    selected_comps = [
        {"name": c.name, "website_url": c.website_url or "", "handle": c.handle or ""}
        for c in req.selected_competitors
    ]
    background_tasks.add_task(
        pipeline_service.run_brand_research_pipeline,
        brand_config_id=db_brand.id,
        brand_name=req.brand_name,
        brand_url=req.website_url,
        category=req.category,
        selected_competitors=selected_comps,
        db_session_factory=async_session,
    )

    return db_brand


# ── GET /api/brands/{brand_id}/status — pipeline status polling ─────────────
@router.get("/{brand_id}/status", response_model=BrandStatusResponse)
async def get_brand_status(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BrandConfig).where(
            BrandConfig.id == brand_id,
            BrandConfig.user_id == current_user.id,
        )
    )
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    return BrandStatusResponse(
        id=brand.id,
        pipeline_status=brand.pipeline_status or "pending",
        social_scraped=(brand.social_metrics == "complete"),
    )
