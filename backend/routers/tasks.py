from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.project import Project

router = APIRouter()


class TaskClassifyRequest(BaseModel):
    prompt: str
    brief_text: Optional[str] = None


# ── POST /api/tasks/classify — phase-1 test endpoint for task_classifier_service ─
@router.post("/classify")
async def classify_task(
    req: TaskClassifyRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Test endpoint for the task classifier (phase 1): classifies a prompt
    (+ optional uploaded brief text) into the single closest task from the
    closed task list in backend/data/task_groups.json. Not yet wired into
    the chat intake flow — that's phase 2.
    """
    from backend.services.task_classifier_service import classify_task as classify

    return classify(req.prompt, req.brief_text)


class TaskIntakeRequest(BaseModel):
    project_id: Optional[str] = None
    brand_config_id: Optional[str] = None
    prompt: str
    brief_text: Optional[str] = None


# ── POST /api/tasks/intake — classify+fill+questions against a real brand context ─
@router.post("/intake")
async def intake(
    req: TaskIntakeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Runs the full task-brief intake (classify_task -> fill_checkpoints ->
    build_questions), read-only.

    Callable two ways — at least one of project_id/brand_config_id is
    required:
      - project_id: current behavior. Ownership check mirrors
        GET /{project_id}/details exactly (404 when the project doesn't
        exist or isn't owned by current_user), then loads that project's
        own BrandConfig.
      - brand_config_id (no Project exists yet, e.g. a fresh task on the
        home-grid path): loads that BrandConfig directly, ownership-checked
        via BrandConfig.user_id == current_user.id (404 otherwise).

    Either way, a missing BrandConfig is NOT an error — brand_context
    degrades to empty/None fields so intake still runs (classify/fill/
    questions all already handle thin-or-no context safely on their own).
    """
    from backend.models.brand import BrandConfig
    from backend.schemas.brand import normalize_target_market, normalize_brand_brief
    from backend.services.task_classifier_service import classify_task
    from backend.services.checkpoint_service import fill_checkpoints, build_questions

    if not req.project_id and not req.brand_config_id:
        raise HTTPException(status_code=422, detail="project_id or brand_config_id is required")

    brand = None
    if req.project_id:
        result = await db.execute(
            select(Project).where(Project.id == req.project_id, Project.user_id == current_user.id)
        )
        project = result.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.brand_config_id:
            brand_result = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
            brand = brand_result.scalars().first()
    else:
        brand_result = await db.execute(
            select(BrandConfig).where(BrandConfig.id == req.brand_config_id, BrandConfig.user_id == current_user.id)
        )
        brand = brand_result.scalars().first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

    brand_context = {
        "brand_brief": normalize_brand_brief(brand.brand_brief if brand else None),
        "target_market": normalize_target_market(brand.target_market if brand else None),
        "additional_notes": (brand.additional_notes or "") if brand else "",
    }

    c = classify_task(req.prompt, req.brief_text)
    f = fill_checkpoints(c["task"], c["group_id"], req.prompt, req.brief_text, brand_context=brand_context)
    q = build_questions(f)

    return {
        "task": c["task"],
        "matched": c["matched"],
        "group_id": c["group_id"],
        "group_name": c["group_name"],
        "agent_type": c["agent_type"],
        "confidence": c["confidence"],
        "checkpoints": f["checkpoints"],
        "missing_required": f["missing_required"],
        "questions": q,
    }
