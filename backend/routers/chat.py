from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.services import registry_service

router = APIRouter()


from backend.schemas.chat import ChatRequest, ChatMessage

# ── GET /api/chat/questions/{title} — agent questionnaire ────────────────────
@router.get("/questions/{title}")
async def get_questions(
    title: str,
    current_user: User = Depends(get_current_user),
):
    """Returns pre-defined onboarding questions for a given agent type."""
    questions = registry_service.get_questions(title) or [
        {"id": "q1", "text": f"What is your primary goal for the {title} initiative?"},
        {"id": "q2", "text": "What timeline and budget constraints should we consider?"},
    ]
    return {"questions": questions}


# ── GET /api/chat/providers — which LLM providers are usable + real models ───
@router.get("/providers")
async def get_providers(
    current_user: User = Depends(get_current_user),
):
    """
    Log-safe provider availability for the model selector: per provider an id,
    display name, whether a key is configured (BOOLEAN only — never any key
    value, prefix, or length), and the model name that would actually run.
    Also reports the report mode and, in advanced mode, the config-pinned
    provider (so the UI can show that a manual selection won't apply).
    """
    from backend.services.ai_service import get_provider_availability
    return get_provider_availability()


# ── POST /api/chat/ — RAG-powered streaming chat ─────────────────────────────
@router.post("/")
async def chat_stream(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Streams an AI response as Server-Sent Events (SSE).
    Uses RAG over the brand's docs/ knowledge base.
    """
    from backend.services.ai_service import stream_chat
    from backend.utils.permissions import has_project_access
    from backend.models.project import Project
    from sqlalchemy.future import select

    proj_res = await db.execute(select(Project).where(Project.id == req.project_id))
    project = proj_res.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to access this project")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def event_generator():
        async for chunk in stream_chat(
            messages=messages,
            project_id=req.project_id,
            db=db,
            provider=req.provider,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
