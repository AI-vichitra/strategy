from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Any, Dict, Optional

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.project import Project

router = APIRouter()


def _build_research_market_prefill(target_market: Dict[str, Any]) -> Dict[str, Any]:
    """v1 best-effort prefill; user can Change. Maps the brand's canonical
    target_market ({region, cities, custom_region} — schemas.brand.
    normalize_target_market's shape) to a tri-level Global/National/Local
    prefill for the Step-3 research market selector. Intentionally lossy for
    region in ("europe", "other") — national stays null there since neither
    maps to one single country. Read-only: never writes back to brand_config;
    this is a per-task prefill only (E15), the brand's own target_market is
    untouched."""
    region = (target_market.get("region") or "").strip().lower()
    cities = [c for c in (target_market.get("cities") or []) if c]
    custom_region = (target_market.get("custom_region") or "").strip()

    if region in ("india", "local"):
        national = "India"  # "local" has no parent country of its own — India is the BRD default
    elif region == "us":
        national = "United States"
    else:  # "europe", "other", "global", "", or anything unrecognized
        national = None

    local = list(cities)
    if custom_region:
        local.append(custom_region)

    return {"global": region == "global", "national": national, "local": local}


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
    from backend.services.task_service import get_research_headings, get_step3_preselected

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
        "research_headings": get_research_headings(),
        "step3_preselected": get_step3_preselected(c["group_id"]),
        "research_market_prefill": _build_research_market_prefill(brand_context["target_market"]),
    }
