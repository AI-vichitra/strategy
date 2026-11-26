from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class TeamBase(BaseModel):
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None

class InitialMemberInvite(BaseModel):
    email: EmailStr
    role: Optional[str] = "member"

class TeamCreate(TeamBase):
    initial_invites: Optional[List[InitialMemberInvite]] = None

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None

class TeamMemberResponse(BaseModel):
    id: str
    team_id: str
    user_id: str
    role: str  # 'admin' | 'member'
    full_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    joined_at: Optional[datetime] = None
    allowed_brands: Optional[List[str]] = None
    allowed_projects: Optional[List[str]] = None

    class Config:
        from_attributes = True

class TeamResponse(TeamBase):
    id: str
    admin_id: str
    created_at: Optional[datetime] = None
    is_admin: bool = False
    role: str = "member"
    members_count: int = 0
    members: Optional[List[TeamMemberResponse]] = None

    class Config:
        from_attributes = True

class InviteMemberRequest(BaseModel):
    email: EmailStr
    team_id: Optional[str] = None
    role: Optional[str] = "member"
    allowed_brands: Optional[List[str]] = None
    allowed_projects: Optional[List[str]] = None

class MemberProjectsUpdateRequest(BaseModel):
    allowed_projects: Optional[List[str]] = None  # None means access to all team projects

class PendingInviteResponse(BaseModel):
    id: str
    email: str
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ResolveInviteResponse(BaseModel):
    email: str
    team_name: Optional[str] = None
    team_id: Optional[str] = None
    invited_by_name: Optional[str] = None
    valid: bool = True
    user_exists: bool = False

class AcceptInviteRequest(BaseModel):
    invite_token: str
