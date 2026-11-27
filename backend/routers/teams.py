import uuid
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_, delete

from backend.dependencies import get_db, get_current_user
from backend.models.user import User
from backend.models.team import Team, TeamMember, PendingInvitation
from backend.models.project import Project
from backend.models.brand import BrandConfig
from backend.schemas.team import (
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamMemberResponse,
    InviteMemberRequest,
    PendingInviteResponse,
    ResolveInviteResponse,
    AcceptInviteRequest,
    MemberProjectsUpdateRequest,
)
from backend.utils.token import generate_reset_token, hash_token
from backend.utils.permissions import get_user_team_ids, has_team_admin_access
from backend.services import email_service

router = APIRouter(prefix="/api/teams", tags=["Teams"])
logger = logging.getLogger(__name__)

MAX_TEAM_MEMBERS = 20  # Limit per team workspace


# ── GET /api/teams/invitations/resolve ───────────────────────────────────────
@router.get("/invitations/resolve", response_model=ResolveInviteResponse)
async def resolve_invitation(token: str, db: AsyncSession = Depends(get_db)):
    """
    Public endpoint: resolve an invite token -> invited email + team name.
    Called by the signup / invite acceptance UI.
    """
    if not token or not token.strip():
        raise HTTPException(status_code=400, detail="Invite token is required")

    hashed = hash_token(token.strip())
    result = await db.execute(
        select(PendingInvitation).where(
            PendingInvitation.invite_token == hashed,
            PendingInvitation.status == "pending"
        )
    )
    invite = result.scalars().first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite token")

    if invite.expires_at and datetime.utcnow() > invite.expires_at:
        invite.status = "expired"
        await db.commit()
        raise HTTPException(status_code=410, detail="Invite token has expired")

    # Get inviter name
    inviter_res = await db.execute(select(User).where(User.id == invite.invited_by_user_id))
    inviter = inviter_res.scalars().first()

    # Check if the invited email already has an account in the system
    existing_user_res = await db.execute(select(User).where(func.lower(User.email) == invite.email.lower()))
    user_exists = existing_user_res.scalars().first() is not None

    return ResolveInviteResponse(
        email=invite.email,
        team_name=invite.team_name or "StratAI Workspace",
        team_id=invite.team_id,
        invited_by_name=inviter.full_name or inviter.email if inviter else None,
        valid=True,
        user_exists=user_exists,
    )


# ── POST /api/teams ──────────────────────────────────────────────────────────
@router.post("", response_model=TeamResponse)
async def create_team(
    payload: TeamCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new team workspace (Admin / Enterprise) with optional initial teammate invites."""
    if getattr(current_user, "role", None) == "member":
        raise HTTPException(status_code=403, detail="You need admin privileges to create a team workspace.")

    team_id = str(uuid.uuid4())
    new_team = Team(
        id=team_id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        avatar_url=payload.avatar_url.strip() if payload.avatar_url else None,
        admin_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(new_team)

    # Automatically add creator as admin member
    member = TeamMember(
        id=str(uuid.uuid4()),
        team_id=team_id,
        user_id=current_user.id,
        role="admin",
        joined_at=datetime.utcnow(),
    )
    db.add(member)

    # Set team_name on user if not already set
    if not current_user.team_name:
        current_user.team_name = payload.name.strip()

    # Process initial teammate invites if provided at creation time
    added_members_count = 1
    if payload.initial_invites:
        for inv in payload.initial_invites:
            clean_email = str(inv.email).lower().strip()
            if not clean_email or clean_email == current_user.email.lower():
                continue

            target_user_res = await db.execute(select(User).where(func.lower(User.email) == clean_email))
            target_user = target_user_res.scalars().first()

            if target_user:
                new_mem = TeamMember(
                    id=str(uuid.uuid4()),
                    team_id=team_id,
                    user_id=target_user.id,
                    role=inv.role or "member",
                    joined_at=datetime.utcnow(),
                )
                db.add(new_mem)
                added_members_count += 1
                if not target_user.parent_user_id and target_user.id != current_user.id:
                    target_user.parent_user_id = current_user.id
                    target_user.role = "member"

                background_tasks.add_task(
                    email_service.send_team_invitation_email,
                    to_email=clean_email,
                    invite_token="existing-user-joined",
                    team_name=new_team.name,
                    inviter_name=current_user.full_name or current_user.email,
                )
            else:
                raw_token = generate_reset_token()
                hashed = hash_token(raw_token)
                expires_at = datetime.utcnow() + timedelta(days=7)
                metadata = json.dumps({"role": inv.role or "member"})

                new_inv = PendingInvitation(
                    id=str(uuid.uuid4()),
                    email=clean_email,
                    invite_token=hashed,
                    invited_by_user_id=current_user.id,
                    team_id=team_id,
                    team_name=new_team.name,
                    status="pending",
                    created_at=datetime.utcnow(),
                    expires_at=expires_at,
                    metadata_json=metadata,
                )
                db.add(new_inv)

                background_tasks.add_task(
                    email_service.send_team_invitation_email,
                    to_email=clean_email,
                    invite_token=raw_token,
                    team_name=new_team.name,
                    inviter_name=current_user.full_name or current_user.email,
                )

    await db.commit()
    await db.refresh(new_team)

    return TeamResponse(
        id=new_team.id,
        name=new_team.name,
        description=new_team.description,
        avatar_url=new_team.avatar_url,
        admin_id=new_team.admin_id,
        created_at=new_team.created_at,
        is_admin=True,
        role="admin",
        members_count=added_members_count,
    )


# ── GET /api/teams ───────────────────────────────────────────────────────────
@router.get("", response_model=List[TeamResponse])
async def get_my_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all teams the current user belongs to or administers."""
    memberships_res = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    memberships = memberships_res.scalars().all()
    user_roles = {m.team_id: m.role for m in memberships}

    # Also include teams where user is direct admin
    owned_res = await db.execute(
        select(Team).where(Team.admin_id == current_user.id)
    )
    owned_teams = owned_res.scalars().all()

    team_ids = set(user_roles.keys()).union(t.id for t in owned_teams)
    if not team_ids:
        return []

    teams_res = await db.execute(
        select(Team).where(Team.id.in_(team_ids)).order_by(Team.created_at.desc())
    )
    teams = teams_res.scalars().all()

    response = []
    for t in teams:
        count_res = await db.execute(
            select(func.count(TeamMember.id)).where(TeamMember.team_id == t.id)
        )
        count = count_res.scalar() or 0
        role = user_roles.get(t.id, "admin" if t.admin_id == current_user.id else "member")
        is_admin = (t.admin_id == current_user.id) or (role == "admin") or (current_user.role == "superadmin")

        response.append(
            TeamResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                avatar_url=t.avatar_url,
                admin_id=t.admin_id,
                created_at=t.created_at,
                is_admin=is_admin,
                role=role,
                members_count=count,
            )
        )
    return response


# ── GET /api/teams/{team_id} ─────────────────────────────────────────────────
@router.get("/{team_id}", response_model=TeamResponse)
async def get_team_details(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get team details and members."""
    team_res = await db.execute(select(Team).where(Team.id == team_id))
    team = team_res.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    user_team_ids = await get_user_team_ids(current_user, db)
    if team_id not in user_team_ids and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="You do not have access to this team")

    # Fetch members with user details
    members_res = await db.execute(
        select(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.joined_at.asc())
    )
    member_rows = members_res.all()

    members_list = []
    current_user_role = "member"
    for tm, u in member_rows:
        if u.id == current_user.id:
            current_user_role = tm.role
        members_list.append(
            TeamMemberResponse(
                id=tm.id,
                team_id=tm.team_id,
                user_id=u.id,
                role=tm.role,
                full_name=u.full_name or u.email.split("@")[0],
                email=u.email,
                avatar_url=u.avatar_url,
                joined_at=tm.joined_at,
                allowed_brands=tm.allowed_brands,
                allowed_projects=tm.allowed_projects,
            )
        )

    is_admin = (team.admin_id == current_user.id) or (current_user_role == "admin") or (current_user.role == "superadmin")

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        avatar_url=team.avatar_url,
        admin_id=team.admin_id,
        created_at=team.created_at,
        is_admin=is_admin,
        role=current_user_role,
        members_count=len(members_list),
        members=members_list,
    )


# ── PATCH /api/teams/{team_id} ───────────────────────────────────────────────
@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    payload: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update team name, description, or avatar (Team Admin only)."""
    if not await has_team_admin_access(team_id, current_user, db):
        raise HTTPException(status_code=403, detail="Only team admins can modify team settings")

    team_res = await db.execute(select(Team).where(Team.id == team_id))
    team = team_res.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if payload.name is not None and payload.name.strip():
        team.name = payload.name.strip()
    if payload.description is not None:
        team.description = payload.description.strip() if payload.description.strip() else None
    if payload.avatar_url is not None:
        team.avatar_url = payload.avatar_url.strip() if payload.avatar_url.strip() else None

    await db.commit()
    await db.refresh(team)

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        avatar_url=team.avatar_url,
        admin_id=team.admin_id,
        created_at=team.created_at,
        is_admin=True,
        role="admin",
    )


# ── POST /api/teams/{team_id}/avatar ─────────────────────────────────────────
@router.post("/{team_id}/avatar", response_model=TeamResponse)
async def upload_team_avatar(
    team_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a logo/avatar image for the team workspace from user local PC (Team Admin only)."""
    if not await has_team_admin_access(team_id, current_user, db):
        raise HTTPException(status_code=403, detail="Only team admins can upload workspace logo")

    team_res = await db.execute(select(Team).where(Team.id == team_id))
    team = team_res.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Logo file exceeds the 5MB size limit")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"]:
        ext = ".png"

    filename = f"team_{team_id}_{uuid.uuid4().hex[:8]}{ext}"
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "teams")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    team.avatar_url = f"/static/uploads/teams/{filename}"
    await db.commit()
    await db.refresh(team)

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        avatar_url=team.avatar_url,
        admin_id=team.admin_id,
        created_at=team.created_at,
        is_admin=True,
        role="admin",
    )


# ── DELETE /api/teams/{team_id}/avatar ───────────────────────────────────────
@router.delete("/{team_id}/avatar", response_model=TeamResponse)
async def remove_team_avatar(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove team workspace logo/avatar (Team Admin only)."""
    if not await has_team_admin_access(team_id, current_user, db):
        raise HTTPException(status_code=403, detail="Only team admins can modify team avatar")

    team_res = await db.execute(select(Team).where(Team.id == team_id))
    team = team_res.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    team.avatar_url = None
    await db.commit()
    await db.refresh(team)

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        avatar_url=None,
        admin_id=team.admin_id,
        created_at=team.created_at,
        is_admin=True,
        role="admin",
    )


# ── DELETE /api/teams/{team_id} ──────────────────────────────────────────────
@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a team workspace (Team Owner only)."""
    team_res = await db.execute(select(Team).where(Team.id == team_id))
    team = team_res.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if team.admin_id != current_user.id and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only the team owner can delete the team")

    # Unlink team from projects and brand configs
    await db.execute(
        select(Project).where(Project.team_id == team_id)
    )
    await db.execute(
        delete(TeamMember).where(TeamMember.team_id == team_id)
    )
    await db.execute(
        delete(PendingInvitation).where(PendingInvitation.team_id == team_id)
    )
    await db.delete(team)
    await db.commit()
    return None


# ── POST /api/teams/{team_id}/invite & /api/teams/invite ─────────────────────
@router.post("/invite")
@router.post("/{team_id}/invite")
async def invite_member(
    payload: InviteMemberRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    team_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invite a user to a team workspace.
    - If user already exists: immediately links them to the team.
    - If user does not exist: creates a pending invitation and emails them an invite link.
    """
    target_team_id = team_id or payload.team_id
    if not target_team_id:
        raise HTTPException(status_code=400, detail="team_id must be provided")

    if not await has_team_admin_access(target_team_id, current_user, db):
        raise HTTPException(status_code=403, detail="You need admin privileges to invite team members.")

    team_res = await db.execute(select(Team).where(Team.id == target_team_id))
    team = team_res.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check capacity limit
    count_res = await db.execute(
        select(func.count(TeamMember.id)).where(TeamMember.team_id == target_team_id)
    )
    current_count = count_res.scalar() or 0
    if current_count >= MAX_TEAM_MEMBERS:
        raise HTTPException(status_code=403, detail=f"Team is full. Maximum {MAX_TEAM_MEMBERS} members allowed.")

    email_clean = payload.email.lower().strip()

    # Automatically assign any selected personal/admin projects to this team workspace
    if payload.allowed_projects:
        for pid in payload.allowed_projects:
            proj_res = await db.execute(select(Project).where(Project.id == pid))
            proj = proj_res.scalars().first()
            if proj and (proj.user_id == current_user.id or current_user.role == "superadmin") and proj.team_id != target_team_id:
                proj.team_id = target_team_id

    # Check if target user already exists in database
    target_user_res = await db.execute(select(User).where(func.lower(User.email) == email_clean))
    target_user = target_user_res.scalars().first()

    if target_user:
        # Check if already a member of this team
        existing_mem_res = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == target_team_id,
                TeamMember.user_id == target_user.id
            )
        )
        existing_mem = existing_mem_res.scalars().first()
        if existing_mem:
            raise HTTPException(status_code=400, detail="User is already a member of this team")

        # Convert/link existing user to this team
        new_mem = TeamMember(
            id=str(uuid.uuid4()),
            team_id=target_team_id,
            user_id=target_user.id,
            role=payload.role or "member",
            allowed_brands=payload.allowed_brands,
            allowed_projects=payload.allowed_projects,
            joined_at=datetime.utcnow(),
        )
        db.add(new_mem)

        # Set parent_user_id if not already set
        if not target_user.parent_user_id and target_user.id != current_user.id:
            target_user.parent_user_id = current_user.id
            target_user.role = "member"

        # Mark any pending invites as accepted
        inv_res = await db.execute(
            select(PendingInvitation).where(
                func.lower(PendingInvitation.email) == email_clean,
                PendingInvitation.team_id == target_team_id
            )
        )
        for inv in inv_res.scalars().all():
            inv.status = "accepted"

        await db.commit()

        # Send notification email in background
        background_tasks.add_task(
            email_service.send_team_invitation_email,
            to_email=email_clean,
            invite_token="existing-user-joined",
            team_name=team.name,
            inviter_name=current_user.full_name or current_user.email,
        )

        return {
            "status": "success",
            "message": f"{email_clean} has been added directly to team '{team.name}'.",
            "team_id": target_team_id,
            "already_registered": True,
        }

    # User does NOT exist yet: create or renew PendingInvitation
    raw_token = generate_reset_token()
    hashed = hash_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(days=7)

    existing_inv_res = await db.execute(
        select(PendingInvitation).where(
            func.lower(PendingInvitation.email) == email_clean,
            PendingInvitation.team_id == target_team_id,
            PendingInvitation.status == "pending"
        )
    )
    existing_inv = existing_inv_res.scalars().first()

    metadata = json.dumps({
        "role": payload.role or "member",
        "allowed_brands": payload.allowed_brands,
        "allowed_projects": payload.allowed_projects,
    })

    if existing_inv:
        existing_inv.invite_token = hashed
        existing_inv.expires_at = expires_at
        existing_inv.metadata_json = metadata
    else:
        new_inv = PendingInvitation(
            id=str(uuid.uuid4()),
            email=email_clean,
            invite_token=hashed,
            invited_by_user_id=current_user.id,
            team_id=target_team_id,
            team_name=team.name,
            status="pending",
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            metadata_json=metadata,
        )
        db.add(new_inv)

    await db.commit()

    # Deliver invite email in background
    background_tasks.add_task(
        email_service.send_team_invitation_email,
        to_email=email_clean,
        invite_token=raw_token,
        team_name=team.name,
        inviter_name=current_user.full_name or current_user.email,
    )

    return {
        "status": "success",
        "message": f"Invitation sent to {email_clean}",
        "team_id": target_team_id,
        "already_registered": False,
    }


# ── POST /api/teams/invitations/accept ───────────────────────────────────────
@router.post("/invitations/accept")
async def accept_invitation(
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a pending team invitation for the logged in user."""
    if not payload.invite_token or not payload.invite_token.strip():
        raise HTTPException(status_code=400, detail="Invite token is required")

    hashed = hash_token(payload.invite_token.strip())
    inv_res = await db.execute(
        select(PendingInvitation).where(
            PendingInvitation.invite_token == hashed
        )
    )
    invite = inv_res.scalars().first()
    if not invite:
        return {
            "status": "success",
            "message": "Invitation already processed or invalid",
            "team_id": None,
        }

    if invite.status == "accepted":
        return {
            "status": "success",
            "message": f"Already joined {invite.team_name or 'the team'}",
            "team_id": invite.team_id,
        }

    if invite.expires_at and datetime.utcnow() > invite.expires_at:
        invite.status = "expired"
        await db.commit()
        return {
            "status": "expired",
            "message": "Invitation has expired",
            "team_id": invite.team_id,
        }

    # Match email
    if invite.email.lower() != current_user.email.lower():
        raise HTTPException(status_code=403, detail="This invitation was addressed to a different email address")

    if not invite.team_id:
        invite.status = "accepted"
        await db.commit()
        return {"status": "success", "message": "Invitation accepted"}

    # Add to team_members
    mem_res = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == invite.team_id,
            TeamMember.user_id == current_user.id
        )
    )
    if not mem_res.scalars().first():
        meta = json.loads(invite.metadata_json) if invite.metadata_json else {}
        db.add(
            TeamMember(
                id=str(uuid.uuid4()),
                team_id=invite.team_id,
                user_id=current_user.id,
                role=meta.get("role", "member"),
                allowed_brands=meta.get("allowed_brands"),
                allowed_projects=meta.get("allowed_projects"),
                joined_at=datetime.utcnow(),
            )
        )

    current_user.role = "member"
    if not current_user.parent_user_id and current_user.id != invite.invited_by_user_id:
        current_user.parent_user_id = invite.invited_by_user_id

    invite.status = "accepted"
    await db.commit()

    return {
        "status": "success",
        "message": f"Successfully joined {invite.team_name or 'the team'}",
        "team_id": invite.team_id,
    }


# ── DELETE /api/teams/{team_id}/members/{user_id} ───────────────────────────
@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from a team (Admin or Self)."""
    team_res = await db.execute(select(Team).where(Team.id == team_id))
    team = team_res.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    is_admin = await has_team_admin_access(team_id, current_user, db)
    is_self = (current_user.id == user_id)

    if not is_admin and not is_self:
        raise HTTPException(status_code=403, detail="Not authorized to remove this member")

    # Cannot remove team owner
    if team.admin_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove the team owner")

    del_res = await db.execute(
        delete(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id
        )
    )
    await db.commit()
    return None


# ── GET /api/teams/{team_id}/projects ─────────────────────────────────────────
@router.get("/{team_id}/projects")
async def get_team_projects(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all projects in this team workspace."""
    user_teams = await get_user_team_ids(current_user, db)
    if team_id not in user_teams and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="You do not have access to this team")

    is_admin = await has_team_admin_access(team_id, current_user, db)

    # Fetch projects in this team with their brand info
    query = (
        select(Project, BrandConfig.brand_name)
        .outerjoin(BrandConfig, Project.brand_config_id == BrandConfig.id)
        .where(Project.team_id == team_id)
        .order_by(Project.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()

    # If regular member, check member.allowed_projects
    allowed_ids = None
    if not is_admin:
        mem_res = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == current_user.id)
        )
        mem = mem_res.scalars().first()
        if mem and mem.allowed_projects is not None:
            allowed_ids = set(str(pid) for pid in mem.allowed_projects)

    projects_list = []
    for proj, brand_name in rows:
        if allowed_ids is not None and str(proj.id) not in allowed_ids:
            continue
        projects_list.append({
            "id": proj.id,
            "title": proj.title,
            "agent_type": proj.agent_type,
            "description": proj.description,
            "brand_config_id": proj.brand_config_id,
            "brand_name": brand_name or "General Strategy",
            "created_at": proj.created_at.isoformat() + "Z" if proj.created_at else None,
            "team_id": proj.team_id,
            "user_id": proj.user_id,
            "is_owner": proj.user_id == current_user.id,
        })

    return projects_list


# ── GET /api/teams/{team_id}/available-projects ──────────────────────────────
@router.get("/{team_id}/available-projects")
async def get_available_projects_to_share(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get personal projects owned by current user that can be given access to this team."""
    if not await has_team_admin_access(team_id, current_user, db):
        raise HTTPException(status_code=403, detail="You need admin privileges to manage team projects")

    # Fetch user's projects that are not yet in this team
    query = (
        select(Project, BrandConfig.brand_name)
        .outerjoin(BrandConfig, Project.brand_config_id == BrandConfig.id)
        .where(
            Project.user_id == current_user.id,
            or_(Project.team_id == None, Project.team_id != team_id)  # noqa: E711
        )
        .order_by(Project.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()

    available = []
    for proj, brand_name in rows:
        available.append({
            "id": proj.id,
            "title": proj.title,
            "agent_type": proj.agent_type,
            "brand_config_id": proj.brand_config_id,
            "brand_name": brand_name or "General Strategy",
            "created_at": proj.created_at.isoformat() + "Z" if proj.created_at else None,
            "current_team_id": proj.team_id,
        })

    return available


# ── POST /api/teams/{team_id}/projects/{project_id} ──────────────────────────
@router.post("/{team_id}/projects/{project_id}")
async def assign_project_to_team(
    team_id: str,
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Give project access to this team workspace (Admin only)."""
    if not await has_team_admin_access(team_id, current_user, db):
        raise HTTPException(status_code=403, detail="You need admin privileges to give project access to this team.")

    proj_res = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_res.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify user owns the project or is superadmin
    if project.user_id != current_user.id and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Not authorized to assign this project")

    project.team_id = team_id
    await db.commit()
    return {"status": "success", "message": f"Project '{project.title}' is now shared with this team.", "team_id": team_id}


# ── DELETE /api/teams/{team_id}/projects/{project_id} ────────────────────────
@router.delete("/{team_id}/projects/{project_id}")
async def revoke_project_from_team(
    team_id: str,
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke project access from this team workspace (Admin only)."""
    if not await has_team_admin_access(team_id, current_user, db):
        raise HTTPException(status_code=403, detail="You need admin privileges to revoke project access.")

    proj_res = await db.execute(select(Project).where(Project.id == project_id, Project.team_id == team_id))
    project = proj_res.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found in this team workspace")

    project.team_id = None
    await db.commit()
    return {"status": "success", "message": f"Project '{project.title}' access revoked from team."}


# ── PATCH /api/teams/{team_id}/members/{user_id}/projects ────────────────────
@router.patch("/{team_id}/members/{user_id}/projects")
async def update_member_project_access(
    team_id: str,
    user_id: str,
    payload: MemberProjectsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update project-level access for a member within the team (Admin only)."""
    if not await has_team_admin_access(team_id, current_user, db):
        raise HTTPException(status_code=403, detail="You need admin privileges to modify member project access.")

    mem_res = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
    )
    member = mem_res.scalars().first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    # Automatically assign any selected personal/admin projects to this team workspace
    if payload.allowed_projects:
        for pid in payload.allowed_projects:
            proj_res = await db.execute(select(Project).where(Project.id == pid))
            proj = proj_res.scalars().first()
            if proj and (proj.user_id == current_user.id or current_user.role == "superadmin") and proj.team_id != team_id:
                proj.team_id = team_id

    member.allowed_projects = payload.allowed_projects
    await db.commit()
    await db.refresh(member)

    return {
        "status": "success",
        "message": "Member project permissions updated successfully.",
        "allowed_projects": member.allowed_projects
    }
