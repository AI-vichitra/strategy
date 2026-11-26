"""
Chat Share API routes (Claude/ChatGPT Style)
Provides snapshot sharing, lightweight message representation, access management
('anyone' vs 'invited'), stop sharing, and 3-day automatic link expiration mechanism.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import JWTError, jwt

from backend.dependencies import get_db, get_current_user, SECRET_KEY, ALGORITHM
from backend.models.user import User
from backend.models.project import Project
from backend.models.message import Message
from backend.models.chat_share import ChatShare
from backend.services import email_service

router = APIRouter(prefix="/api/chat", tags=["Chat Share"])


class CreateShareRequest(BaseModel):
    project_id: str
    access_type: Optional[str] = "anyone"  # Default: anyone with the link
    invited_emails: Optional[List[str]] = []


class UpdateShareRequest(BaseModel):
    access_type: Optional[str] = None
    invited_emails: Optional[List[str]] = None
    refresh_snapshot: Optional[bool] = False
    renew_expiration: Optional[bool] = False


class RequestAccessPayload(BaseModel):
    email: Optional[str] = None
    message: Optional[str] = None


class SendInvitationsRequest(BaseModel):
    emails: List[str]
    custom_message: Optional[str] = None
    share_url: Optional[str] = None
    project_id: Optional[str] = None


async def get_optional_current_user(request: Request, db: AsyncSession) -> Optional[User]:
    """Helper to detect authenticated user on public routes if Bearer header or cookie is present."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.cookies.get("token") or request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()
    except (JWTError, Exception):
        return None


async def _build_snapshot_messages(project_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
    """Build lightweight snapshot of project messages."""
    result = await db.execute(
        select(Message)
        .where(Message.project_id == project_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    snapshot = []
    for msg in messages:
        snapshot.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content or "",
            "created_at": msg.created_at.isoformat() + "Z" if msg.created_at else None,
            "message_metadata": msg.message_metadata,
        })
    return snapshot


@router.post("/share")
async def create_or_update_share(
    payload: CreateShareRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new snapshot share or updates an existing share for the project/chat.
    Each share link is valid for 3 days (72 hours).
    """
    result = await db.execute(select(Project).where(Project.id == payload.project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Chat project not found")

    from backend.utils.permissions import has_project_access
    if not await has_project_access(project, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to share this chat")

    snapshot = await _build_snapshot_messages(project.id, db)

    access_type = payload.access_type if payload.access_type in ["anyone", "invited"] else "anyone"
    clean_emails = [e.strip().lower() for e in (payload.invited_emails or []) if e and "@" in e]

    share_res = await db.execute(
        select(ChatShare).where(
            ChatShare.project_id == project.id,
            ChatShare.user_id == current_user.id
        )
    )
    share = share_res.scalars().first()

    owner_name = current_user.full_name or (
        current_user.email.split("@")[0].replace(".", " ").title() if current_user.email else "User"
    )
    now = datetime.utcnow()
    three_days_later = now + timedelta(days=3)

    if share:
        share.is_active = True
        share.title = project.title or "Shared Chat"
        share.owner_name = owner_name
        share.owner_email = current_user.email
        share.access_type = access_type
        if clean_emails:
            existing = set(share.invited_emails or [])
            existing.update(clean_emails)
            share.invited_emails = list(existing)
        share.snapshot_messages = snapshot
        share.expires_at = three_days_later
        share.updated_at = now
    else:
        share = ChatShare(
            id=str(uuid.uuid4()),
            project_id=project.id,
            user_id=current_user.id,
            title=project.title or "Shared Chat",
            owner_name=owner_name,
            owner_email=current_user.email,
            access_type=access_type,
            invited_emails=clean_emails,
            access_requests=[],
            snapshot_messages=snapshot,
            is_active=True,
            expires_at=three_days_later,
            created_at=now,
            updated_at=now
        )
        db.add(share)

    await db.commit()
    await db.refresh(share)

    if clean_emails:
        for em in clean_emails:
            background_tasks.add_task(
                email_service.send_chat_invitation_email,
                to_email=em,
                inviter_name=owner_name,
                inviter_email=current_user.email,
                chat_title=share.title,
                share_url=f"/share/{share.id}"
            )

    return {
        "share_id": share.id,
        "share_url": f"/share/{share.id}",
        "title": share.title,
        "access_type": share.access_type,
        "invited_emails": share.invited_emails or [],
        "owner_name": share.owner_name,
        "owner_email": share.owner_email,
        "message_count": len(share.snapshot_messages) if share.snapshot_messages else 0,
        "expires_at": share.expires_at.isoformat() + "Z" if share.expires_at else None,
        "created_at": share.created_at.isoformat() + "Z" if share.created_at else None,
    }


@router.get("/share/settings/{project_id}")
async def get_share_settings(
    project_id: str,
    auto_create: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves current share configuration for a chat project.
    If auto_create=True and no share exists yet, initializes one on demand.
    """
    share_res = await db.execute(
        select(ChatShare).where(
            ChatShare.project_id == project_id,
            ChatShare.user_id == current_user.id
        )
    )
    share = share_res.scalars().first()

    if not share or not share.is_active:
        if auto_create:
            proj_res = await db.execute(select(Project).where(Project.id == project_id))
            project = proj_res.scalars().first()

            if not project:
                raise HTTPException(status_code=404, detail="Chat project not found")

            from backend.utils.permissions import has_project_access
            if not await has_project_access(project, current_user, db):
                raise HTTPException(status_code=403, detail="Not authorized to share this chat")

            snapshot = await _build_snapshot_messages(project.id, db)
            owner_name = current_user.full_name or (
                current_user.email.split("@")[0].replace(".", " ").title() if current_user.email else "User"
            )
            now = datetime.utcnow()
            three_days_later = now + timedelta(days=3)

            share = ChatShare(
                id=str(uuid.uuid4()),
                project_id=project.id,
                user_id=current_user.id,
                title=project.title or "Shared Chat",
                owner_name=owner_name,
                owner_email=current_user.email,
                access_type="anyone",
                invited_emails=[],
                access_requests=[],
                snapshot_messages=snapshot,
                is_active=True,
                expires_at=three_days_later,
                created_at=now,
                updated_at=now
            )
            db.add(share)
            await db.commit()
            await db.refresh(share)

            return {
                "shared": True,
                "share_id": share.id,
                "share_url": f"/share/{share.id}",
                "title": share.title,
                "access_type": share.access_type,
                "invited_emails": [],
                "access_requests": [],
                "owner_name": share.owner_name,
                "owner_email": share.owner_email,
                "message_count": len(snapshot),
                "is_expired": False,
                "expires_at": share.expires_at.isoformat() + "Z" if share.expires_at else None,
                "updated_at": share.updated_at.isoformat() + "Z" if share.updated_at else None,
            }

        return {"shared": False}

    now = datetime.utcnow()
    is_expired = bool(share.expires_at and now > share.expires_at)

    return {
        "shared": True,
        "share_id": share.id,
        "share_url": f"/share/{share.id}",
        "title": share.title,
        "access_type": share.access_type,
        "invited_emails": share.invited_emails or [],
        "access_requests": share.access_requests or [],
        "owner_name": share.owner_name,
        "owner_email": share.owner_email,
        "message_count": len(share.snapshot_messages) if share.snapshot_messages else 0,
        "is_expired": is_expired,
        "expires_at": share.expires_at.isoformat() + "Z" if share.expires_at else None,
        "updated_at": share.updated_at.isoformat() + "Z" if share.updated_at else None,
    }


@router.put("/share/{share_id}")
async def update_share_settings(
    share_id: str,
    payload: UpdateShareRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates access settings, adds/removes invited emails, or renews expiration.
    """
    share_res = await db.execute(
        select(ChatShare).where(
            ChatShare.id == share_id,
            ChatShare.user_id == current_user.id
        )
    )
    share = share_res.scalars().first()

    if not share:
        raise HTTPException(status_code=404, detail="Shared chat not found")

    owner_name = share.owner_name or current_user.full_name or (
        current_user.email.split("@")[0].replace(".", " ").title() if current_user.email else "User"
    )

    if payload.access_type and payload.access_type in ["anyone", "invited"]:
        share.access_type = payload.access_type

    if payload.invited_emails is not None:
        clean_emails = [e.strip().lower() for e in payload.invited_emails if e and "@" in e]
        share.invited_emails = clean_emails

    if payload.refresh_snapshot:
        share.snapshot_messages = await _build_snapshot_messages(share.project_id, db)

    if payload.renew_expiration:
        share.expires_at = datetime.utcnow() + timedelta(days=3)
        share.is_active = True

    share.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(share)

    if clean_emails:
        for em in clean_emails:
            background_tasks.add_task(
                email_service.send_chat_invitation_email,
                to_email=em,
                inviter_name=owner_name,
                inviter_email=current_user.email,
                chat_title=share.title,
                share_url=f"/share/{share.id}"
            )

    return {
        "share_id": share.id,
        "share_url": f"/share/{share.id}",
        "title": share.title,
        "access_type": share.access_type,
        "invited_emails": share.invited_emails or [],
        "message_count": len(share.snapshot_messages) if share.snapshot_messages else 0,
        "expires_at": share.expires_at.isoformat() + "Z" if share.expires_at else None,
        "updated_at": share.updated_at.isoformat() + "Z" if share.updated_at else None,
    }


@router.post("/share/{share_id}/invite")
async def send_chat_invitations(
    share_id: str,
    payload: SendInvitationsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sends email invitations to the specified recipients for a shared chat.
    Validates ownership, saves invited_emails in DB, and dispatches emails via SMTP.
    """
    share_res = await db.execute(
        select(ChatShare).where(
            ChatShare.id == share_id,
            ChatShare.user_id == current_user.id
        )
    )
    share = share_res.scalars().first()

    if not share:
        raise HTTPException(status_code=404, detail="Shared chat not found or unauthorized")

    clean_emails = [e.strip().lower() for e in payload.emails if e and "@" in e]
    if not clean_emails:
        raise HTTPException(status_code=400, detail="No valid email addresses provided")

    # Add to invited_emails list in DB if not already present
    existing_invited = set(share.invited_emails or [])
    existing_invited.update(clean_emails)
    share.invited_emails = list(existing_invited)
    share.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(share)

    inviter_name = current_user.full_name or (
        current_user.email.split("@")[0].replace(".", " ").title() if current_user.email else "A colleague"
    )
    inviter_email = current_user.email or "ai@vichitraa.agency"
    share_path = payload.share_url or f"/share/{share.id}"

    # Queue background tasks to send invitations via SMTP
    for email in clean_emails:
        background_tasks.add_task(
            email_service.send_chat_invitation_email,
            to_email=email,
            inviter_name=inviter_name,
            inviter_email=inviter_email,
            chat_title=share.title or "Strategy Report",
            share_url=share_path,
            custom_message=payload.custom_message,
        )

    return {
        "success": True,
        "invited_count": len(clean_emails),
        "invited_emails": share.invited_emails,
        "message": f"Invitations successfully dispatched to {len(clean_emails)} recipient(s)."
    }


@router.post("/share/invite")
async def send_invitations_generic(
    payload: SendInvitationsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generic invitation endpoint accepting either share_id or project_id.
    """
    if payload.share_id:
        return await send_chat_invitations(
            share_id=payload.share_id,
            payload=payload,
            background_tasks=background_tasks,
            db=db,
            current_user=current_user
        )

    if not payload.project_id:
        raise HTTPException(status_code=400, detail="Either share_id or project_id must be provided")

    # Look up or create share for this project
    share_res = await db.execute(
        select(ChatShare).where(
            ChatShare.project_id == payload.project_id,
            ChatShare.user_id == current_user.id
        )
    )
    share = share_res.scalars().first()

    if not share:
        # Auto-create share if not existing
        proj_res = await db.execute(select(Project).where(Project.id == payload.project_id))
        project = proj_res.scalars().first()
        if not project or project.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized")

        snapshot = await _build_snapshot_messages(project.id, db)
        owner_name = current_user.full_name or (
            current_user.email.split("@")[0].replace(".", " ").title() if current_user.email else "User"
        )
        now = datetime.utcnow()
        share = ChatShare(
            id=str(uuid.uuid4()),
            project_id=project.id,
            user_id=current_user.id,
            title=project.title or "Shared Chat",
            owner_name=owner_name,
            owner_email=current_user.email,
            access_type="invited",
            invited_emails=[],
            access_requests=[],
            snapshot_messages=snapshot,
            is_active=True,
            expires_at=now + timedelta(days=3),
            created_at=now,
            updated_at=now
        )
        db.add(share)
        await db.commit()
        await db.refresh(share)

    return await send_chat_invitations(
        share_id=share.id,
        payload=payload,
        background_tasks=background_tasks,
        db=db,
        current_user=current_user
    )


@router.delete("/share/{share_id}")
async def stop_sharing(
    share_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deactivates a chat share link.
    """
    share_res = await db.execute(
        select(ChatShare).where(
            ChatShare.id == share_id,
            ChatShare.user_id == current_user.id
        )
    )
    share = share_res.scalars().first()

    if not share:
        raise HTTPException(status_code=404, detail="Shared chat not found")

    share.is_active = False
    share.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "Sharing stopped successfully."}


@router.get("/shared/{share_id}")
async def get_public_shared_chat(
    share_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Public snapshot retrieval endpoint.
    Validates link existence, active status, expiration, and access permissions.
    """
    share_res = await db.execute(select(ChatShare).where(ChatShare.id == share_id))
    share = share_res.scalars().first()

    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "This shared chat link does not exist."}
        )

    if not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SHARING_STOPPED",
                "title": share.title,
                "owner_name": share.owner_name or "the owner",
                "message": f"The owner ({share.owner_name or 'the owner'}) has stopped sharing this conversation."
            }
        )

    now = datetime.utcnow()
    if share.expires_at and now > share.expires_at:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": "LINK_EXPIRED",
                "title": share.title,
                "owner_name": share.owner_name or "the owner",
                "owner_email": share.owner_email,
                "expired_at": share.expires_at.isoformat() + "Z",
                "message": f"This shared chat link has expired. Please request a new link from {share.owner_name or 'the owner'} to view the content."
            }
        )

    caller = await get_optional_current_user(request, db)

    # Access control: 'anyone' vs 'invited'
    if share.access_type == "invited":
        is_owner = caller and caller.id == share.user_id
        is_invited = False
        if caller and caller.email:
            caller_email = caller.email.lower().strip()
            invited = [e.lower().strip() for e in (share.invited_emails or [])]
            is_invited = caller_email in invited

        if not is_owner and not is_invited:
            if not caller:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": "AUTH_REQUIRED",
                        "title": share.title,
                        "owner_name": share.owner_name or "the owner",
                        "owner_email": share.owner_email,
                        "message": "This conversation is restricted to invited members. Please log in with your invited email."
                    }
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "ACCESS_RESTRICTED",
                    "title": share.title,
                    "owner_name": share.owner_name or "the owner",
                    "owner_email": share.owner_email,
                    "user_email": caller.email,
                    "message": f"Your account ({caller.email}) has not been invited to view this chat. You can request access from {share.owner_name or 'the owner'}."
                }
            )

    return {
        "share_id": share.id,
        "title": share.title,
        "owner_name": share.owner_name,
        "owner_email": share.owner_email,
        "created_at": share.created_at.isoformat() + "Z" if share.created_at else None,
        "expires_at": share.expires_at.isoformat() + "Z" if share.expires_at else None,
        "messages": share.snapshot_messages or [],
        "access_type": share.access_type,
    }


@router.post("/shared/{share_id}/request-access")
async def request_share_access(
    share_id: str,
    payload: RequestAccessPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a viewer's request for access to an invited-only shared chat.
    Notifies the chat owner by email.
    """
    share_res = await db.execute(select(ChatShare).where(ChatShare.id == share_id))
    share = share_res.scalars().first()

    if not share or not share.is_active:
        raise HTTPException(status_code=404, detail="Shared chat not found or inactive")

    caller = await get_optional_current_user(request, db)
    req_email = (payload.email or (caller.email if caller else None) or "").strip().lower()

    if not req_email or "@" not in req_email:
        raise HTTPException(status_code=400, detail="A valid email is required to request access")

    requests = list(share.access_requests or [])
    # Check if already requested
    already = any(r.get("email", "").lower() == req_email for r in requests)
    if not already:
        requests.append({
            "email": req_email,
            "requested_at": datetime.utcnow().isoformat() + "Z",
            "message": payload.message or "",
            "status": "pending"
        })
        share.access_requests = requests
        share.updated_at = datetime.utcnow()
        await db.commit()

        # Notify chat owner by email via SMTP
        if share.owner_email:
            custom_note = f"<p><strong>Note from viewer:</strong> <em>{payload.message}</em></p>" if payload.message else ""
            background_tasks.add_task(
                email_service.send_email,
                to_email=share.owner_email,
                subject=f"Access requested: '{share.title}' on StratAI",
                html_body=f"""
                <div style="font-family: sans-serif; color: #1A1A1A; padding: 20px;">
                    <h2>Access Request for Your Shared Strategy</h2>
                    <p><strong>{req_email}</strong> has requested access to view your shared chat: <strong>{share.title}</strong>.</p>
                    {custom_note}
                    <p>Log in to StratAI to add them to your invited members list.</p>
                </div>
                """,
                text_body=f"{req_email} has requested access to view '{share.title}'. Log in to StratAI to approve access."
            )

    return {"success": True, "message": "Access request submitted to the owner."}
