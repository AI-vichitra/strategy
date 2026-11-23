from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional, Tuple
from datetime import datetime
import json
import logging
import os
import uuid

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.project import Project
from backend.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, CompetitorDetail, BrandKit
from backend.schemas.report import ReportMetadata
from backend.schemas.brand import normalize_target_market
from backend.services import report_service
from backend.services.brand_theme import extract_palette_from_logo, _decode_logo_image, _looks_like_svg, _LOGO_FORMAT_EXTENSIONS

from sqlalchemy.orm import selectinload

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_COMPETITORS = 5

_LOGO_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "logos")
_MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
_ACCEPTED_LOGO_FORMATS_MSG = "png, jpg, jpeg, webp, gif, bmp, tiff, svg"


def _serialize_competitor_details(competitors: Optional[List[CompetitorDetail]]) -> Optional[str]:
    """Validates (max 5) and serializes competitor details to a JSON string for storage.
    None (field absent) → stored as None, which triggers the onboarding fallback on the report path.
    Empty list [] → stored as "[]", meaning the user explicitly cleared competitors (no fallback)."""
    if competitors is None:
        return None
    if len(competitors) > MAX_COMPETITORS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_COMPETITORS} competitors are allowed")
    return json.dumps([c.model_dump() for c in competitors])


def _serialize_brand_kit(brand_kit: Optional[BrandKit]) -> Optional[str]:
    """Serializes the brand kit to a JSON string for storage.
    None or an empty brand kit both mean "clear" and are stored as None."""
    if brand_kit is None:
        return None
    data = brand_kit.model_dump()
    if not data.get("logo_url") and not data.get("colors"):
        return None
    return json.dumps(data)


def _resolve_logo_bytes(brand_kit: Optional[BrandKit]) -> Tuple[Optional[bytes], Optional[str]]:
    """Reads the brand kit's logo file off disk (same lookup brand_theme.py uses
    at export time) and returns (bytes, mime) to persist on the Project row, so
    the DB — not the ephemeral filesystem — is what export-time reads rely on.
    Returns (None, None) if there's no logo or the file isn't there (missing
    files are skipped the same way brand_theme._load_logo_asset does)."""
    if brand_kit is None or not brand_kit.logo_url:
        return None, None
    import mimetypes
    from backend.services.brand_theme import _resolve_logo_path
    path = _resolve_logo_path(brand_kit.logo_url)
    if not path:
        return None, None
    try:
        with open(path, "rb") as f:
            data = f.read()
        mime, _ = mimetypes.guess_type(path)
        return data, mime or "application/octet-stream"
    except Exception:
        logger.warning("Could not read logo at %s to persist to DB", path, exc_info=True)
        return None, None


@router.post("/upload-logo")
async def upload_logo(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    contents = await file.read()
    if len(contents) > _MAX_LOGO_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="Logo file exceeds the 2MB size limit")

    # Format is detected from the file's own bytes (not the client-supplied
    # filename/content-type, which can lie) by running it through the same
    # decoder the export path uses — if it can't be decoded here, it couldn't
    # be used in an export either.
    try:
        img = _decode_logo_image(contents)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported or corrupt image file. Allowed formats: {_ACCEPTED_LOGO_FORMATS_MSG}",
        )
    # Store the original bytes under an extension matching the detected format
    # (SVG is kept as the original vector file, not the rasterized preview
    # `img` is decoded into — rasterization happens again, from this file, at
    # export time via the same chokepoint).
    ext = ".svg" if _looks_like_svg(contents) else (_LOGO_FORMAT_EXTENSIONS.get(img.format) or ".png")

    filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(_LOGO_UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(_LOGO_UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    logo_url = f"/static/uploads/logos/{filename}"
    response = {"logo_url": logo_url}
    try:
        palette = extract_palette_from_logo(logo_url)
        if palette:
            response["palette"] = palette
    except Exception:
        logger.warning("Palette extraction failed for %s", logo_url, exc_info=True)
    return response


@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    competitor_details_json = _serialize_competitor_details(project.competitor_details)
    brand_kit_json = _serialize_brand_kit(project.brand_kit)
    logo_data, logo_mime = _resolve_logo_bytes(project.brand_kit)

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
            p.brand_kit = brand_kit_json
            p.logo_data = logo_data
            p.logo_mime = logo_mime
            p.created_at = datetime.utcnow()
            await db.commit()
            res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == p.id))
            return res.scalars().first()

    # Otherwise create a new chat project for this brand
    project_data = project.model_dump(exclude={"competitor_details", "brand_kit"})
    db_project = Project(**project_data, competitor_details=competitor_details_json, brand_kit=brand_kit_json, logo_data=logo_data, logo_mime=logo_mime, user_id=current_user.id)
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
    if "brand_kit" in update_data:
        update_data["brand_kit"] = _serialize_brand_kit(project_update.brand_kit)
        update_data["logo_data"], update_data["logo_mime"] = _resolve_logo_bytes(project_update.brand_kit)
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

@router.get("/{project_id}/details")
async def get_project_details(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.brand import BrandConfig

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    brand_result = await db.execute(
        select(BrandConfig).where(BrandConfig.id == project.brand_config_id)
    )
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    logo_url = None
    colors = None
    if project.brand_kit:
        try:
            bk = json.loads(project.brand_kit)
            logo_url = bk.get("logo_url")
            colors = bk.get("colors")
        except Exception:
            pass
    # Fallback: look for brand_kit from any sibling project when this one has none
    if not logo_url and not colors and project.brand_config_id:
        fb_result = await db.execute(
            select(Project.brand_kit)
            .where(
                Project.brand_config_id == project.brand_config_id,
                Project.user_id == current_user.id,
                Project.brand_kit.isnot(None),
                Project.id != project.id,
            )
            .order_by(Project.created_at.asc())
            .limit(1)
        )
        fb_raw = fb_result.scalar_one_or_none()
        if fb_raw:
            try:
                fb_bk = json.loads(fb_raw)
                logo_url = fb_bk.get("logo_url")
                colors = fb_bk.get("colors")
            except Exception:
                pass

    competitors_selected = []
    if brand.competitors:
        try:
            for c in json.loads(brand.competitors):
                competitors_selected.append({
                    "name": c.get("name", ""),
                    "website_url": c.get("url") or c.get("website_url") or "",
                })
        except Exception:
            pass

    competitors_used = []
    kb_raw = brand.kb_json  # DB is the source of truth; file is a local-cache fallback below
    if kb_raw is None and brand.brand_slug:
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        kb_path = os.path.join(_root, "KNOWLEDGE_BASE", f"{brand.brand_slug}_KB.json")
        # Migration fallback: new slugs are {BRAND_SLUG}_{project_id[:8]}; if the new KB
        # doesn't exist, try the brand-name-only slug for projects created before the fix.
        if not os.path.exists(kb_path):
            parts = brand.brand_slug.rsplit('_', 1)
            if len(parts) == 2 and len(parts[1]) == 8:
                fallback = os.path.join(_root, "KNOWLEDGE_BASE", f"{parts[0]}_KB.json")
                if os.path.exists(fallback):
                    kb_path = fallback
        if os.path.exists(kb_path):
            try:
                with open(kb_path, "r", encoding="utf-8") as f:
                    kb_raw = f.read()
            except Exception:
                kb_raw = None
    if kb_raw:
        try:
            kb = json.loads(kb_raw)
            for c in kb.get("competitors", []):
                competitors_used.append({
                    "name": c.get("NAME", ""),
                    "website_url": c.get("URL", ""),
                })
        except Exception:
            pass

    last_updated = None
    if project.last_active_at:
        last_updated = project.last_active_at.isoformat()
    elif project.created_at:
        last_updated = project.created_at.isoformat()

    # Collect all chat projects for this brand, ordered newest first
    chats_result = await db.execute(
        select(Project)
        .options(selectinload(Project.messages))
        .where(Project.brand_config_id == project.brand_config_id, Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    all_chats = chats_result.scalars().all()
    chats = []
    for c in all_chats:
        msgs = c.messages or []
        last_msg_at = max((m.created_at for m in msgs), default=None)
        chats.append({
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "last_message_at": last_msg_at.isoformat() if last_msg_at else None,
            "message_count": len(msgs),
        })

    return {
        "brand_config_id": project.brand_config_id,
        "brand": {
            "name": brand.brand_name,
            "website_url": brand.website_url,
            "category": brand.category,
            "region": None,
            "target_market": normalize_target_market(brand.target_market),
            "brand_context": brand.brand_context,
            "logo_url": logo_url,
            "colors": colors,
        },
        "competitors_selected": competitors_selected,
        "competitors_used": competitors_used,
        "chats": chats,
        "status": brand.pipeline_status,
        "created_at": brand.created_at.isoformat() if brand.created_at else None,
        "last_updated": last_updated,
    }


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import delete
    from backend.models.report import Report
    from backend.models.report_section import ReportSection
    from backend.models.report_share import ReportShare

    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. Clean up report child rows that have no ORM cascade (ReportSection, ReportShare)
    report_rows = await db.execute(select(Report.id).where(Report.project_id == project_id))
    report_ids = [r[0] for r in report_rows.all()]
    if report_ids:
        await db.execute(delete(ReportSection).where(ReportSection.report_id.in_(report_ids)))
        await db.execute(delete(ReportShare).where(ReportShare.report_id.in_(report_ids)))

    # 2. Delete the project — ORM cascade (Project.messages / Project.reports,
    # both cascade="all, delete-orphan") removes Message and Report rows.
    # Neither FK has an ON DELETE CASCADE at the DB level (confirmed against
    # the live SQLite schema), so the ORM cascade is the ONLY delete
    # mechanism for them — do not also issue a manual bulk DELETE here, or
    # the ORM's own cascade-delete will match 0 rows and log a SAWarning.
    await db.delete(project)
    await db.commit()

    return {"detail": "Chat project and messages deleted from database"}
