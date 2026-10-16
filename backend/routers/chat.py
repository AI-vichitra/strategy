from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional

from backend.dependencies import get_db, get_current_user
from backend.models.user import User

router = APIRouter()


from backend.schemas.chat import ChatRequest, ChatMessage

# ── GET /api/chat/questions/{title} — agent questionnaire ────────────────────
@router.get("/questions/{title}")
async def get_questions(
    title: str,
    current_user: User = Depends(get_current_user),
):
    """Returns pre-defined onboarding questions for a given agent type."""
    questions_map = {
        "Competition Analysis": [
            {"id": "q1", "text": "Which specific competitors concern you most and why?"},
            {"id": "q2", "text": "What market or geography should we focus on?"},
            {"id": "q3", "text": "What differentiators do you believe you have over competitors?"},
        ],
        "GTM Strategy": [
            {"id": "q1", "text": "Who is your primary target customer segment?"},
            {"id": "q2", "text": "What channels (digital, offline, partnerships) are you prioritising?"},
            {"id": "q3", "text": "What is your launch timeline and budget range?"},
        ],
        "Product Launch Strategy": [
            {"id": "q1", "text": "What are you launching?"},
            {"id": "q2", "text": "What is the primary objective of this launch?"},
            {"id": "q3", "text": "What is your planned launch timeline?"},
        ],
        "Social Media Strategy": [
            {"id": "q1", "text": "Which social platforms are most important for your brand?"},
            {"id": "q2", "text": "What is your current posting frequency and content mix?"},
            {"id": "q3", "text": "What specific social media outcomes do you want to improve?"},
        ],
        "Brand Audit": [
            {"id": "q1", "text": "How would you describe your current brand positioning?"},
            {"id": "q2", "text": "What do customers currently say about your brand?"},
            {"id": "q3", "text": "Which brand elements feel outdated or misaligned?"},
        ],
    }
    questions = questions_map.get(title, [
        {"id": "q1", "text": f"What is your primary goal for the {title} initiative?"},
        {"id": "q2", "text": "What timeline and budget constraints should we consider?"},
    ])
    return {"questions": questions}


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
