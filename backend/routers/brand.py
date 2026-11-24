from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
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
    BrandContextResearchRequest,
    BrandBriefRequest,
    TARGET_MARKET_CONFIG,
    extract_instagram_username,
)

router = APIRouter()


# ── GET /api/brands/target-market-config — region/city config ──────────────
@router.get("/target-market-config")
async def get_target_market_config(
    current_user: User = Depends(get_current_user),
):
    """
    Backend-owned single source of truth for Target Market region options and
    their curated per-region city lists. The frontend fetches this instead of
    keeping its own hardcoded copy.
    """
    return TARGET_MARKET_CONFIG

_ALLOWED_REFERENCE_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
_MAX_REFERENCE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1 of brand setup: Runs Tavily to discover competitors (optionally
    enriched by the hybrid LLM-resolver engine, see tavily_service.py).
    Returns candidate list for the frontend to display.
    Does NOT save anything to the DB yet.
    """
    from backend.services import tavily_service, connector_service, logo_scraper_service

    # Resolved async (DB connector lookup -> FIRECRAWL_API_KEY env fallback),
    # mirroring pipeline_service's existing pattern, then handed to the
    # executor as a plain string — never blocks the request on a failed lookup.
    firecrawl_key = None
    try:
        firecrawl_key = await connector_service.get_api_key(
            db, user_id=current_user.id, connector_id="firecrawl", env_fallback="FIRECRAWL_API_KEY"
        )
    except Exception:
        firecrawl_key = None

    result = await __import__("asyncio").get_event_loop().run_in_executor(
        None,
        lambda: tavily_service.search_competitors(
            brand_name=req.brand_name,
            category=req.category,
            website_url=req.website_url,
            user_competitors=[c.model_dump() for c in (req.user_competitors or [])],
            industry=req.industry,
            region=req.region,
            target_market=req.target_market.model_dump() if req.target_market else None,
            reference_ref_ids=req.reference_ref_ids,
            firecrawl_key=firecrawl_key,
        ),
    )

    # Scrape logos concurrently for candidates AND brand's own website
    items_to_scrape = []
    if req.website_url:
        items_to_scrape.append({"url": req.website_url, "name": req.brand_name})
    for c in result.get("candidates", []):
        c_url = c.get("website_url") or c.get("url")
        if c_url:
            items_to_scrape.append({"url": c_url, "name": c.get("name", "")})

    logos_map = await __import__("asyncio").get_event_loop().run_in_executor(
        None,
        lambda: logo_scraper_service.scrape_logos_concurrently(items_to_scrape)
    )

    brand_logo = logos_map.get(req.website_url) or logo_scraper_service.get_google_fallback_logo_url(req.website_url)
    result["brand_logo_url"] = brand_logo

    for c in result.get("candidates", []):
        c_url = c.get("website_url") or c.get("url")
        c_logo = logos_map.get(c_url) or (logo_scraper_service.get_google_fallback_logo_url(c_url) if c_url else "")
        # Safeguard: competitor logo must never borrow or collide with the primary brand's logo
        if c_logo and brand_logo and c_logo == brand_logo:
            c_logo = ""
        c["logo_url"] = c_logo

    return result


# ── POST /api/brands/research-context — auto-fill brand context ────────────
@router.post("/research-context")
async def research_context(
    req: BrandContextResearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Brand-setup wizard "Research Brand" button: best-effort Tavily search +
    LLM summarization of the brand's context. Never errors on failure — an
    empty context (and empty sources) means auto-research couldn't verify
    anything, and the frontend falls back to manual entry.
    """
    from backend.services import brand_context_service

    summary, sources = await __import__("asyncio").get_event_loop().run_in_executor(
        None,
        lambda: brand_context_service._research_brand_context_full(
            brand_name=req.brand_name,
            website_url=req.website_url,
            category=req.category,
        ),
    )
    return {"context": summary, "sources": sources}


# ── POST /api/brands/generate-brief — structured 6-field Brand Brief ───────
@router.post("/generate-brief")
async def generate_brief(
    req: BrandBriefRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Brand-setup wizard: generates the structured Brand Brief from whatever
    onboarding-time evidence is available — a direct fetch of the brand's
    own website text, uploaded reference docs, the same two Tavily queries
    brand_context_service already runs, and category/target_market/
    additional_notes. The richer Tavily research pipeline (web_scrape/
    deep_dive/risk/depth) does not exist yet at this point in the flow, so
    the brief is only as grounded as these inputs.

    Always returns the 6-key dict, never an error — brand_brief_service
    degrades to an all-"" shape on any failure (missing LLM key, completion
    error, unparseable response), same non-blocking contract as
    research-context/extract-social-links.
    """
    from backend.services import social_links_service, brand_context_service, brand_brief_service, reference_service, connector_service

    # Firecrawl key: DB connector lookup -> FIRECRAWL_API_KEY env fallback, the
    # same resolution search_competitors already uses. Resolved async here and
    # handed to the executor as a plain string; a failed lookup just means no
    # JS-render fallback for a thin website (never blocks brief generation).
    firecrawl_key = None
    try:
        firecrawl_key = await connector_service.get_api_key(
            db, user_id=current_user.id, connector_id="firecrawl", env_fallback="FIRECRAWL_API_KEY"
        )
    except Exception:
        firecrawl_key = None

    def _collect_reference_text() -> str:
        if not req.reference_docs:
            return ""
        parts = []
        for doc in req.reference_docs:
            ref_id = doc.get("ref_id")
            if not ref_id:
                continue
            text = reference_service.load_reference_text(ref_id)
            if text:
                parts.append(f"[{doc.get('filename', '')}]\n{text}")
        return "\n\n".join(parts)

    def _run():
        website_text = social_links_service.extract_page_text(req.website_url, firecrawl_key=firecrawl_key)
        reference_docs_text = _collect_reference_text()
        tavily_context, tavily_sources = brand_context_service._research_brand_context_full(
            brand_name=req.brand_name,
            website_url=req.website_url,
            category=req.category,
        )
        return brand_brief_service.generate_brand_brief(
            brand_name=req.brand_name,
            category=req.category,
            target_market=req.target_market.model_dump() if req.target_market else None,
            additional_notes=req.additional_notes or "",
            website_text=website_text,
            reference_docs_text=reference_docs_text,
            tavily_context=tavily_context,
            tavily_sources=tavily_sources,
        )

    result = await __import__("asyncio").get_event_loop().run_in_executor(None, _run)
    return result


# ── GET /api/brands/extract-social-links — scan a website for profile links ─
@router.get("/extract-social-links")
async def extract_social_links(
    website_url: str,
    current_user: User = Depends(get_current_user),
):
    """
    Brand-setup wizard: best-effort scan of the brand's own website for links
    to its social profiles, to pre-fill a user-verify step. Always returns
    200 with a dict (possibly empty) — a blocked, slow, or broken site must
    never fail onboarding.
    """
    from backend.services import social_links_service

    result = await __import__("asyncio").get_event_loop().run_in_executor(
        None, lambda: social_links_service.extract_social_links(website_url)
    )
    return result


# ── POST /api/brands/upload-reference — brand-setup reference doc upload ────
@router.post("/upload-reference")
async def upload_reference(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Brand-setup wizard only: uploads one reference document (.pdf/.docx/.txt/.md,
    max 10MB), extracts its text, and returns {ref_id, filename, char_count} for
    the frontend to collect and post back in BrandConfirmRequest.reference_docs.
    One file per call; the frontend calls this once per selected file.
    """
    import os
    from backend.services import reference_service

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_REFERENCE_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Unsupported file type. Allowed: pdf, docx, txt, md")

    contents = await file.read()
    if len(contents) > _MAX_REFERENCE_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="Reference document exceeds the 10MB size limit")

    try:
        return reference_service.save_reference(file.filename, contents)
    except RuntimeError as e:
        # Missing PDF extraction library — surfaced as a clear client error, not a 500.
        raise HTTPException(status_code=422, detail=str(e))


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
    from backend.services import pipeline_service, reference_service, logo_scraper_service
    from backend.routers.projects import _serialize_brand_kit, _serialize_competitor_details, _resolve_logo_bytes
    from backend.schemas.project import CompetitorDetail, BrandKit

    # Resolve brand logo: user-supplied in brand_kit or scraped from website
    brand_logo = None
    if req.brand_kit and req.brand_kit.logo_url:
        brand_logo = req.brand_kit.logo_url
    elif req.website_url:
        brand_logo = logo_scraper_service.scrape_and_save_logo(req.website_url, req.brand_name)
        if brand_logo:
            if not req.brand_kit:
                req.brand_kit = BrandKit(logo_url=brand_logo)
            else:
                req.brand_kit.logo_url = brand_logo

    # Create BrandConfig
    competitors_json = json.dumps([
        {"name": c.name, "url": c.website_url or "", "logo_url": c.logo_url or ""}
        for c in req.selected_competitors
    ])
    # Embed each reference doc's extracted text into the JSON now (not just
    # {ref_id, filename}) so BrandConfig.reference_docs is the source of truth
    # for every later pipeline run, surviving a restart that wipes the disk file.
    reference_docs_with_text = None
    if req.reference_docs:
        reference_docs_with_text = []
        for doc in req.reference_docs:
            ref_id = doc.get("ref_id")
            entry = dict(doc)
            entry["text"] = reference_service.load_reference_text(ref_id) if ref_id else ""
            reference_docs_with_text.append(entry)
    reference_docs_json = json.dumps(reference_docs_with_text) if reference_docs_with_text else None
    target_market_json = json.dumps(req.target_market.model_dump()) if req.target_market else None

    # social_handles is optional and not yet sent by the frontend. When it IS
    # present and carries an instagram entry, that becomes the source of truth
    # for the legacy brand_handle column (bare username, no URL) — otherwise
    # brand_handle falls back to whatever the (today's) frontend sent directly.
    social_handles_json = json.dumps(req.social_handles) if req.social_handles else None
    brand_handle_value = req.brand_handle
    if req.social_handles and req.social_handles.get("instagram"):
        brand_handle_value = extract_instagram_username(req.social_handles["instagram"])

    # brand_brief is optional and not yet sent by the UI; brand_context keeps
    # being written exactly as it is today, unaffected by this.
    brand_brief_json = json.dumps(req.brand_brief) if req.brand_brief else None

    db_brand = BrandConfig(
        user_id=current_user.id,
        brand_name=req.brand_name,
        website_url=req.website_url,
        category=req.category,
        logo_url=brand_logo,
        brand_context=req.brand_context,
        additional_notes=req.additional_notes,
        competitors=competitors_json,
        brand_handle=brand_handle_value,
        social_handles=social_handles_json,
        brand_brief=brand_brief_json,
        reference_docs=reference_docs_json,
        target_market=target_market_json,
        pipeline_status="pending",
    )
    db.add(db_brand)
    await db.commit()
    await db.refresh(db_brand)

    # Create default Project
    logo_data, logo_mime = _resolve_logo_bytes(req.brand_kit)
    comp_details_list = [
        CompetitorDetail(brand_name=c.name, website_url=c.website_url, logo_url=c.logo_url)
        for c in req.selected_competitors
    ]
    db_project = Project(
        user_id=current_user.id,
        brand_config_id=db_brand.id,
        agent_type="StratAI",
        title=req.brand_name,
        description="Auto-created project",
        competitor_details=_serialize_competitor_details(comp_details_list),
        brand_kit=_serialize_brand_kit(req.brand_kit),
        logo_data=logo_data,
        logo_mime=logo_mime,
    )
    db.add(db_project)
    await db.commit()

    # Launch pipeline in background — user is redirected immediately
    selected_comps = [
        {"name": c.name, "website_url": c.website_url or "", "handle": c.handle or "", "logo_url": c.logo_url or ""}
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
        project_id=db_project.id,
    )

    return db_brand


# ── DELETE /api/brands/{brand_id} ───────────────────────────────────────────
@router.put("/{brand_id}")
async def update_brand(
    brand_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BrandConfig).where(BrandConfig.id == brand_id, BrandConfig.user_id == current_user.id)
    )
    brand = result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if "brand_name" in payload and payload["brand_name"]:
        brand.brand_name = payload["brand_name"].strip()
        proj_result = await db.execute(
            select(Project).where(Project.brand_config_id == brand.id, Project.user_id == current_user.id)
        )
        for p in proj_result.scalars().all():
            p.title = brand.brand_name
    await db.commit()
    await db.refresh(brand)
    return {"id": brand.id, "brand_name": brand.brand_name}


# ── DELETE /api/brands/{brand_id} ───────────────────────────────────────────
@router.delete("/{brand_id}")
async def delete_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete a brand that has no linked projects.
    Returns 404 if brand doesn't exist or isn't owned by the caller.
    Returns 409 if the brand still has projects (delete those first).
    Does NOT touch docs/, KNOWLEDGE_BASE/, or uploaded logo files.
    """
    result = await db.execute(
        select(BrandConfig).where(
            BrandConfig.id == brand_id,
            BrandConfig.user_id == current_user.id,
        )
    )
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Refuse if any project still references this brand
    proj_result = await db.execute(
        select(Project.id).where(Project.brand_config_id == brand_id).limit(1)
    )
    if proj_result.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="This brand still has projects. Delete all projects for this brand first, then retry.",
        )

    await db.delete(brand)
    await db.commit()
    return {"detail": "Brand deleted"}


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
