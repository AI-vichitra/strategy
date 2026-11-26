from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional, Tuple
from datetime import datetime
import json
import logging
import os
import uuid
from jose import jwt

from backend.dependencies import get_db, get_current_user, get_current_user_optional, SECRET_KEY, ALGORITHM
from backend.models.user import User
from backend.models.project import Project
from backend.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, CompetitorDetail, BrandKit
from backend.schemas.report import ReportMetadata
from backend.schemas.brand import (
    normalize_target_market,
    normalize_brand_brief,
    normalize_social_handles,
    BrandBriefUpdate,
    SocialHandlesUpdate,
    BrandContextUpdate,
    ReferenceDocAdd,
)
from backend.services import report_service
from backend.services.brand_theme import extract_palette_from_logo, _decode_logo_image, _looks_like_svg, _LOGO_FORMAT_EXTENSIONS

from sqlalchemy.orm import selectinload
from sqlalchemy import func
from backend.models.message import Message

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
    from backend.models.brand import BrandConfig

    # Auto-resolve brand name and verify multi-tenant brand ownership/access
    if project.brand_config_id:
        from backend.utils.permissions import has_brand_access
        brand_res = await db.execute(
            select(BrandConfig).where(BrandConfig.id == project.brand_config_id)
        )
        b = brand_res.scalars().first()
        if not b:
            raise HTTPException(status_code=404, detail="Brand not found")
        if not await has_brand_access(b, current_user, db):
            raise HTTPException(status_code=403, detail="Not authorized to create a project for this brand")
        if not project.title or project.title in ("New Strategy Chat", "New Project", "StratAI"):
            project.title = b.brand_name

    if project.team_id:
        from backend.utils.permissions import get_user_team_ids
        user_team_ids = await get_user_team_ids(current_user, db)
        if project.team_id not in user_team_ids and current_user.role != "superadmin":
            raise HTTPException(status_code=403, detail="Not authorized to assign project to this team")

    competitor_details_json = _serialize_competitor_details(project.competitor_details)
    brand_kit_json = _serialize_brand_kit(project.brand_kit)
    logo_data, logo_mime = _resolve_logo_bytes(project.brand_kit)

    # 1. Reuse an existing unused project (0 messages) for this brand in the same scope if available
    existing_result = await db.execute(
        select(Project)
        .options(selectinload(Project.messages))
        .where(
            Project.user_id == current_user.id,
            Project.brand_config_id == project.brand_config_id,
            Project.team_id == project.team_id,
        )
        .order_by(Project.created_at.desc())
    )
    existing_projects = existing_result.scalars().all()
    for p in existing_projects:
        msg_cnt_res = await db.execute(select(func.count(Message.id)).where(Message.project_id == p.id))
        msg_cnt = msg_cnt_res.scalar() or 0
        if msg_cnt == 0:
            p.title = project.title
            p.agent_type = project.agent_type
            if project.llm_provider:
                p.llm_provider = project.llm_provider
            p.competitor_details = competitor_details_json
            p.brand_kit = brand_kit_json
            p.logo_data = logo_data
            p.logo_mime = logo_mime
            p.team_id = project.team_id
            p.created_at = datetime.utcnow()
            await db.commit()
            res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == p.id))
            return res.scalars().first()

    # 2. If a project with the same agent_type and title already exists for this brand and scope, reuse it to prevent duplicates
    if project.agent_type:
        for p in existing_projects:
            same_agent = (p.agent_type or "").strip().lower() == project.agent_type.strip().lower()
            same_title = (p.title or "").strip().lower() == (project.title or "").strip().lower()
            if same_agent and same_title:
                if competitor_details_json:
                    p.competitor_details = competitor_details_json
                if brand_kit_json:
                    p.brand_kit = brand_kit_json
                if logo_data:
                    p.logo_data = logo_data
                    p.logo_mime = logo_mime
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
async def get_projects(
    team_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.utils.permissions import get_user_team_ids, has_team_admin_access
    from backend.models.team import TeamMember
    from sqlalchemy import or_

    user_team_ids = await get_user_team_ids(current_user, db)

    if team_id:
        if team_id not in user_team_ids and current_user.role != "superadmin":
            raise HTTPException(status_code=403, detail="You do not have access to this team's projects")
        query = select(Project).options(selectinload(Project.messages)).where(Project.team_id == team_id)
        result = await db.execute(query.order_by(Project.created_at.desc()))
        all_projects = result.scalars().all()

        # If regular member, filter by allowed_projects if restricted
        if not await has_team_admin_access(team_id, current_user, db):
            mem_res = await db.execute(
                select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == current_user.id)
            )
            member = mem_res.scalars().first()
            if member and member.allowed_projects is not None:
                allowed_ids = set(str(pid) for pid in member.allowed_projects)
                all_projects = [p for p in all_projects if str(p.id) in allowed_ids]
        return all_projects
    else:
        conditions = [Project.user_id == current_user.id]
        if current_user.parent_user_id:
            conditions.append(Project.user_id == current_user.parent_user_id)
        if user_team_ids:
            conditions.append(Project.team_id.in_(user_team_ids))
        query = select(Project).options(selectinload(Project.messages)).where(or_(*conditions))

        result = await db.execute(query.order_by(Project.created_at.desc()))
        all_projects = result.scalars().all()

        # For any team project in the list, verify member-level access
        filtered_projects = []
        member_cache = {}
        for p in all_projects:
            if p.team_id and p.user_id != current_user.id:
                if p.team_id not in member_cache:
                    is_adm = await has_team_admin_access(p.team_id, current_user, db)
                    if is_adm:
                        member_cache[p.team_id] = None  # None means admin / no restriction
                    else:
                        m_res = await db.execute(
                            select(TeamMember).where(TeamMember.team_id == p.team_id, TeamMember.user_id == current_user.id)
                        )
                        m = m_res.scalars().first()
                        member_cache[p.team_id] = m.allowed_projects if (m and m.allowed_projects is not None) else None
                allowed = member_cache[p.team_id]
                if allowed is not None and str(p.id) not in [str(x) for x in allowed]:
                    continue
            filtered_projects.append(p)
        return filtered_projects

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from backend.utils.permissions import has_project_access
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.messages))
        .where(Project.id == project_id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    return project

@router.get("/{project_id}/logo")
async def get_project_logo(
    project_id: str,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # If query token is provided and current_user is not resolved, authenticate via token
    if not current_user and token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email:
                u_res = await db.execute(select(User).where(User.email == email))
                current_user = u_res.scalars().first()
        except Exception:
            pass

    from backend.utils.permissions import has_project_access
    if current_user:
        if not await has_project_access(project, current_user, db):
            raise HTTPException(status_code=403, detail="Not authorized to access this project's logo")
    else:
        # Check if project has an active public share
        from backend.models.chat_share import ChatShare
        share_res = await db.execute(
            select(ChatShare).where(ChatShare.project_id == project_id, ChatShare.is_active == True)
        )
        if not share_res.scalars().first():
            raise HTTPException(status_code=401, detail="Authentication required to view project logo")
    
    # 1. If project has raw logo_data BLOB
    if project.logo_data:
        return Response(content=project.logo_data, media_type=project.logo_mime or "image/png")
    
    # 2. If project has brand_kit logo_url
    if project.brand_kit:
        try:
            bk = json.loads(project.brand_kit) if isinstance(project.brand_kit, str) else project.brand_kit
            logo_url = bk.get("logo_url")
            if logo_url and logo_url.startswith("/static/"):
                file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), logo_url.lstrip("/").replace("/", os.sep))
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        data = f.read()
                    mime = "image/svg+xml" if file_path.endswith(".svg") else "image/png"
                    return Response(content=data, media_type=mime)
        except Exception:
            pass

    # 3. If linked to brand_config
    if project.brand_config_id:
        from backend.models.brand import BrandConfig
        b_res = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
        brand = b_res.scalars().first()
        if brand and brand.logo_url and brand.logo_url.startswith("/static/"):
            file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), brand.logo_url.lstrip("/").replace("/", os.sep))
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    data = f.read()
                mime = "image/svg+xml" if file_path.endswith(".svg") else "image/png"
                return Response(content=data, media_type=mime)

    raise HTTPException(status_code=404, detail="Logo not found")

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, project_update: ProjectUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from backend.utils.permissions import has_project_access
    result = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")
    
    update_data = project_update.model_dump(exclude_unset=True)
    if "competitor_details" in update_data:
        update_data["competitor_details"] = _serialize_competitor_details(project_update.competitor_details)
    if "brand_kit" in update_data:
        update_data["brand_kit"] = _serialize_brand_kit(project_update.brand_kit)
        update_data["logo_data"], update_data["logo_mime"] = _resolve_logo_bytes(project_update.brand_kit)
    for key, value in update_data.items():
        setattr(project, key, value)

    # If title is updated and project is linked to a BrandConfig, sync brand_name
    if "title" in update_data and project.brand_config_id:
        from backend.models.brand import BrandConfig
        brand_result = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
        brand = brand_result.scalars().first()
        if brand and (brand.user_id == current_user.id or project.team_id):
            brand.brand_name = project.title

    await db.commit()
    res = await db.execute(select(Project).options(selectinload(Project.messages)).where(Project.id == project_id))
    return res.scalars().first()

@router.get("/{project_id}/reports", response_model=List[ReportMetadata])
async def get_project_reports(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from backend.utils.permissions import has_project_access, has_brand_access
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        # Check if project_id is actually a brand_config_id
        from backend.models.brand import BrandConfig
        brand_res = await db.execute(select(BrandConfig).where(BrandConfig.id == project_id))
        brand = brand_res.scalars().first()
        if brand:
            if not await has_brand_access(brand, current_user, db):
                return []
            proj_res = await db.execute(select(Project).where(Project.brand_config_id == brand.id))
            proj = proj_res.scalars().first()
            if proj and await has_project_access(proj, current_user, db):
                return await report_service.list_reports(db, proj.id)
            return []
        # Return empty list rather than 404 for deleted/merged projects or non-existent
        return []

    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to view reports for this project")

    return await report_service.list_reports(db, project_id)

@router.get("/{project_id}/details")
async def get_project_details(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.brand import BrandConfig
    from backend.utils.permissions import has_project_access, has_brand_access

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    
    brand = None
    if project:
        if not await has_project_access(project, current_user, db):
            raise HTTPException(status_code=403, detail="Not authorized to access this project's details")
        brand_result = await db.execute(
            select(BrandConfig).where(BrandConfig.id == project.brand_config_id)
        )
        brand = brand_result.scalars().first()
    else:
        # Check if project_id is actually a brand_config_id
        brand_result = await db.execute(
            select(BrandConfig).where(BrandConfig.id == project_id)
        )
        brand = brand_result.scalars().first()
        if brand:
            if not await has_brand_access(brand, current_user, db):
                raise HTTPException(status_code=403, detail="Not authorized to access this brand's details")
            proj_result = await db.execute(
                select(Project).where(Project.brand_config_id == brand.id).order_by(Project.created_at.desc())
            )
            for p in proj_result.scalars().all():
                if await has_project_access(p, current_user, db):
                    project = p
                    break
        else:
            raise HTTPException(status_code=404, detail="Project or Brand not found")

    if not brand:
        raise HTTPException(status_code=404, detail="Project or Brand not found")

    logo_url = brand.logo_url or None
    colors = None
    if project and project.brand_kit:
        try:
            bk = json.loads(project.brand_kit)
            logo_url = bk.get("logo_url") or logo_url
            colors = bk.get("colors")
        except Exception:
            pass
    # Fallback: look for brand_kit from any sibling project when this one has none
    if not logo_url and not colors and project and project.brand_config_id:
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
                logo_url = fb_bk.get("logo_url") or logo_url
                colors = fb_bk.get("colors")
            except Exception:
                pass

    competitors_selected = []
    if brand.competitors:
        try:
            for c in json.loads(brand.competitors):
                c_logo = c.get("logo_url") or ""
                # Safeguard: prevent showing the brand's own logo for a competitor
                if c_logo and brand.logo_url and c_logo == brand.logo_url:
                    c_logo = ""
                if c_logo and logo_url and c_logo == logo_url:
                    c_logo = ""
                competitors_selected.append({
                    "name": c.get("name", ""),
                    "website_url": c.get("url") or c.get("website_url") or "",
                    "logo_url": c_logo,
                })
        except Exception:
            pass

    reference_docs_list = []
    if brand.reference_docs:
        try:
            for doc in json.loads(brand.reference_docs):
                reference_docs_list.append({
                    "ref_id": doc.get("ref_id", ""),
                    "filename": doc.get("filename", ""),
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
    if project and project.last_active_at:
        last_updated = project.last_active_at.isoformat()
    elif project and project.created_at:
        last_updated = project.created_at.isoformat()
    elif brand.created_at:
        last_updated = brand.created_at.isoformat()

    # Collect all chat projects for this brand that current_user has access to, ordered newest first
    chats_result = await db.execute(
        select(Project)
        .options(selectinload(Project.messages))
        .where(Project.brand_config_id == brand.id)
        .order_by(Project.created_at.desc())
    )
    all_chats = chats_result.scalars().all()
    accessible_chats = []
    for c in all_chats:
        if await has_project_access(c, current_user, db):
            accessible_chats.append(c)

    chats = []
    seen_chat_keys = set()
    for c in accessible_chats:
        chat_key = (c.agent_type or "").strip().lower() or (c.title or "").strip().lower()
        if chat_key in seen_chat_keys:
            continue
        seen_chat_keys.add(chat_key)
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
        "brand_config_id": brand.id,
        "brand": {
            "name": brand.brand_name,
            "website_url": brand.website_url,
            "category": brand.category,
            "region": None,
            "target_market": normalize_target_market(brand.target_market),
            "brand_context": brand.brand_context,
            "brand_brief": normalize_brand_brief(brand.brand_brief),
            "social_handles": normalize_social_handles(brand.social_handles, brand.brand_handle),
            "logo_url": logo_url,
            "colors": colors,
            "reference_docs": reference_docs_list,
        },
        "competitors_selected": competitors_selected,
        "competitors_used": competitors_used,
        "chats": chats,
        "status": brand.pipeline_status,
        "created_at": brand.created_at.isoformat() if brand.created_at else None,
        "last_updated": last_updated,
    }


@router.put("/{project_id}/brand-brief")
async def update_brand_brief(
    project_id: str,
    payload: BrandBriefUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.brand import BrandConfig
    from backend.utils.permissions import has_project_access, has_brand_access

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")

    brand_result = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not await has_brand_access(brand, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this brand")

    data = payload.model_dump()
    if not any(v.strip() for v in data.values()):
        raise HTTPException(status_code=422, detail="At least one instruction field is required")

    brand.brand_brief = json.dumps(data)
    await db.commit()
    return {"status": "ok"}


@router.put("/{project_id}/social-handles")
async def update_social_handles(
    project_id: str,
    payload: SocialHandlesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.brand import BrandConfig
    from backend.utils.permissions import has_project_access, has_brand_access

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")

    brand_result = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not await has_brand_access(brand, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this brand")

    data = payload.model_dump()
    if not any(v.strip() for v in data.values()):
        raise HTTPException(status_code=422, detail="At least one social handle is required")

    brand.social_handles = json.dumps(data)
    await db.commit()
    return {"status": "ok"}


@router.put("/{project_id}/brand-context")
async def update_brand_context(
    project_id: str,
    payload: BrandContextUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.brand import BrandConfig
    from backend.utils.permissions import has_project_access, has_brand_access

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")

    brand_result = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not await has_brand_access(brand, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this brand")

    if not payload.website_url.strip() or not payload.category.strip() or not payload.target_market.strip():
        raise HTTPException(status_code=422, detail="website_url, category, and target_market are all required")

    brand.website_url = payload.website_url
    brand.category = payload.category
    brand.target_market = payload.target_market
    await db.commit()
    return {"status": "ok"}


@router.put("/{project_id}/reference-docs")
async def add_reference_doc(
    project_id: str,
    payload: ReferenceDocAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.brand import BrandConfig
    from backend.services import reference_service
    from backend.utils.permissions import has_project_access, has_brand_access

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")

    brand_result = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not await has_brand_access(brand, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this brand")

    try:
        docs = json.loads(brand.reference_docs) if brand.reference_docs else []
    except Exception:
        docs = []

    if not any(d.get("ref_id") == payload.ref_id for d in docs):
        text = reference_service.load_reference_text(payload.ref_id)
        docs.append({"ref_id": payload.ref_id, "filename": payload.filename, "text": text})
        brand.reference_docs = json.dumps(docs)

        # Fold the new doc into the already-compiled kb_json — the only thing the
        # RAG index/prompt read at generation time — so it reaches the NEXT report
        # without a full pipeline re-run. Mirrors pipeline_service.py:646-664
        # exactly (same label format, same prepend-ahead-of-existing order).
        # No explicit cache eviction needed: ai_service._get_or_build_index keys
        # its cache on a hash of kb_json's own content, so writing a changed
        # kb_json here means the next call computes a different hash and
        # rebuilds automatically.
        kb_patched = False
        if brand.kb_json:
            try:
                kb = json.loads(brand.kb_json)
            except Exception:
                kb = None
            if isinstance(kb, dict) and isinstance(kb.get("brand"), dict):
                existing = kb["brand"].get("WEB_SCRAPPED", "")
                block = f"[Source: Reference Document — {payload.filename}]\n{text}"
                kb["brand"]["WEB_SCRAPPED"] = block + "\n\n" + existing
                brand.kb_json = json.dumps(kb)
                kb_patched = True

        if kb_patched:
            logger.info(f"[REF-DOC] folded {payload.filename} into kb_json for {brand.brand_slug}, index cache invalidated")
        else:
            logger.warning(f"[REF-DOC] kb_json not present, doc stored but not folded into KB for {project_id}")

        await db.commit()

    return {
        "status": "ok",
        "reference_docs": [{"ref_id": d.get("ref_id", ""), "filename": d.get("filename", "")} for d in docs],
    }


@router.delete("/{project_id}/reference-docs/{ref_id}")
async def delete_reference_doc(
    project_id: str,
    ref_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.brand import BrandConfig
    from backend.utils.permissions import has_project_access, has_brand_access

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")

    brand_result = await db.execute(select(BrandConfig).where(BrandConfig.id == project.brand_config_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if not await has_brand_access(brand, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to modify this brand")

    try:
        docs = json.loads(brand.reference_docs) if brand.reference_docs else []
    except Exception:
        docs = []

    entry = next((d for d in docs if d.get("ref_id") == ref_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Reference document not found")

    filename = entry.get("filename", "")
    text = entry.get("text", "")

    # Reverse the exact fold the add path (and the onboarding pipeline,
    # pipeline_service.py:646-664) applied, so a removed doc also leaves the
    # RAG corpus, not just the reference_docs list.
    if brand.kb_json:
        try:
            kb = json.loads(brand.kb_json)
        except Exception:
            kb = None
        if isinstance(kb, dict) and isinstance(kb.get("brand"), dict):
            block = f"[Source: Reference Document — {filename}]\n{text}"
            web_scrapped = kb["brand"].get("WEB_SCRAPPED", "")
            if block + "\n\n" in web_scrapped:
                web_scrapped = web_scrapped.replace(block + "\n\n", "", 1)
            elif "\n\n" + block in web_scrapped:
                web_scrapped = web_scrapped.replace("\n\n" + block, "", 1)
            elif block in web_scrapped:
                web_scrapped = web_scrapped.replace(block, "", 1)
            else:
                logger.warning(f"[REF-DOC] block not found in kb_json for {ref_id} (left kb unchanged)")
            kb["brand"]["WEB_SCRAPPED"] = web_scrapped
            brand.kb_json = json.dumps(kb)
        else:
            logger.warning(f"[REF-DOC] kb_json not present, doc removed but not unfolded from KB for {project_id}")
    else:
        logger.warning(f"[REF-DOC] kb_json not present, doc removed but not unfolded from KB for {project_id}")

    docs = [d for d in docs if d.get("ref_id") != ref_id]
    brand.reference_docs = json.dumps(docs)
    await db.commit()

    logger.info(f"[REF-DOC] deleted {filename} ({ref_id}) from project {project_id}")

    return {
        "status": "ok",
        "reference_docs": [{"ref_id": d.get("ref_id", ""), "filename": d.get("filename", "")} for d in docs],
    }


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import delete
    from backend.models.report import Report
    from backend.models.report_section import ReportSection
    from backend.models.report_share import ReportShare
    from backend.utils.permissions import has_project_admin_access

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await has_project_admin_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to delete this project. Only project creator, team admin, or system admin can delete.")

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

    return {"detail": "Chat project and messages deleted from database"}
