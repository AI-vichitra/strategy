from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.models.user import User
from backend.models.team import Team, TeamMember
from backend.models.project import Project
from backend.models.brand import BrandConfig


async def get_user_team_ids(user: User, db: AsyncSession) -> List[str]:
    """Returns all team IDs the user is a member of or owns."""
    if not user:
        return []

    # 1. Teams where user is an active member
    mem_result = await db.execute(select(TeamMember.team_id).where(TeamMember.user_id == user.id))
    team_ids = set(mem_result.scalars().all())

    # 2. Teams where user is the admin/owner
    owner_result = await db.execute(select(Team.id).where(Team.admin_id == user.id))
    team_ids.update(owner_result.scalars().all())

    # 3. If user is an admin, they also have oversight over teams created by their members
    if getattr(user, "role", None) == "admin":
        member_res = await db.execute(select(User.id).where(User.parent_user_id == user.id))
        member_ids = member_res.scalars().all()
        if member_ids:
            member_teams = await db.execute(select(Team.id).where(Team.admin_id.in_(member_ids)))
            team_ids.update(member_teams.scalars().all())

    return list(team_ids)


async def has_team_admin_access(team_id: str, user: User, db: AsyncSession) -> bool:
    """Checks if the user has admin/owner rights over a team."""
    if not user or not team_id:
        return False
    if getattr(user, "role", None) == "superadmin":
        return True

    # Check direct team ownership
    res = await db.execute(select(Team).where(Team.id == team_id))
    team = res.scalars().first()
    if not team:
        return False
    if team.admin_id == user.id:
        return True

    # Check member role == 'admin'
    mem_res = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user.id)
    )
    mem = mem_res.scalars().first()
    if mem and mem.role == "admin":
        return True

    return False


async def has_project_access(project: Project, user: User, db: AsyncSession) -> bool:
    """Checks whether the user has read/write access to the given project/chat."""
    if not project or not user:
        return False
    if getattr(user, "role", None) == "superadmin":
        return True

    # 1. Direct owner
    if str(project.user_id) == str(user.id):
        return True

    # 2. Team project: strictly governed by team membership
    if project.team_id:
        user_teams = await get_user_team_ids(user, db)
        if project.team_id in user_teams:
            # If user is team admin/owner, full access to all team projects
            if await has_team_admin_access(project.team_id, user, db):
                return True
            # For regular member, check allowed_projects
            mem_res = await db.execute(
                select(TeamMember).where(TeamMember.team_id == project.team_id, TeamMember.user_id == user.id)
            )
            member = mem_res.scalars().first()
            if member:
                allowed = member.allowed_projects
                if isinstance(allowed, str):
                    import json
                    try:
                        allowed = json.loads(allowed)
                    except Exception:
                        allowed = None
                if not allowed or str(project.id) in [str(p) for p in allowed]:
                    return True
                return False
            return True
        return False

    # 3. Personal project (no team_id):
    # - Parent admin accessing sub-account's project (administrative oversight)
    proj_owner_res = await db.execute(select(User).where(User.id == project.user_id))
    proj_owner = proj_owner_res.scalars().first()
    if proj_owner and proj_owner.parent_user_id and str(proj_owner.parent_user_id) == str(user.id):
        return True

    return False


async def has_project_admin_access(project: Project, user: User, db: AsyncSession) -> bool:
    """Checks whether the user has administrator permissions on the project (e.g. to delete it)."""
    if not project or not user:
        return False
    if getattr(user, "role", None) == "superadmin":
        return True

    # 1. Direct owner/creator
    if str(project.user_id) == str(user.id):
        return True

    # 2. If it's a team project, team admin or team owner can administer it
    if project.team_id:
        if await has_team_admin_access(project.team_id, user, db):
            return True
        return False

    # 3. Parent account of the project creator
    proj_owner_res = await db.execute(select(User).where(User.id == project.user_id))
    proj_owner = proj_owner_res.scalars().first()
    if proj_owner and proj_owner.parent_user_id and str(proj_owner.parent_user_id) == str(user.id):
        return True

    return False


async def has_brand_access(brand: BrandConfig, user: User, db: AsyncSession) -> bool:
    """Checks whether the user has access to the brand configuration."""
    if not brand or not user:
        return False
    if getattr(user, "role", None) == "superadmin":
        return True

    # 1. Direct owner
    if str(brand.user_id) == str(user.id):
        return True

    # 2. Parent / sub-account access
    if user.parent_user_id and str(brand.user_id) == str(user.parent_user_id):
        return True

    brand_owner_res = await db.execute(select(User).where(User.id == brand.user_id))
    brand_owner = brand_owner_res.scalars().first()
    if brand_owner and brand_owner.parent_user_id and str(brand_owner.parent_user_id) == str(user.id):
        return True

    # 3. Team workspace brand
    if brand.team_id:
        user_teams = await get_user_team_ids(user, db)
        if brand.team_id in user_teams:
            # Check allowed_brands if configured on TeamMember
            mem_res = await db.execute(
                select(TeamMember).where(TeamMember.team_id == brand.team_id, TeamMember.user_id == user.id)
            )
            member = mem_res.scalars().first()
            if member:
                allowed_b = member.allowed_brands
                if isinstance(allowed_b, str):
                    import json
                    try:
                        allowed_b = json.loads(allowed_b)
                    except Exception:
                        allowed_b = None
                if not allowed_b or str(brand.id) in [str(b) for b in allowed_b]:
                    return True
                return False
            else:
                # User is admin/owner of the team
                return True

    return False


async def has_brand_admin_access(brand: BrandConfig, user: User, db: AsyncSession) -> bool:
    """Checks whether the user has administrator permissions on the brand (e.g. to delete it)."""
    if not brand or not user:
        return False
    if getattr(user, "role", None) == "superadmin":
        return True

    # 1. Direct owner/creator
    if str(brand.user_id) == str(user.id):
        return True

    # 2. Team brand
    if brand.team_id:
        if await has_team_admin_access(brand.team_id, user, db):
            return True
        return False

    # 3. Parent account of owner
    brand_owner_res = await db.execute(select(User).where(User.id == brand.user_id))
    brand_owner = brand_owner_res.scalars().first()
    if brand_owner and brand_owner.parent_user_id and str(brand_owner.parent_user_id) == str(user.id):
        return True

    return False


async def has_report_access(report: Any, user: User, db: AsyncSession) -> bool:
    """Checks whether the user has access to view, export, or edit a report."""
    if not report or not user:
        return False
    if getattr(user, "role", None) == "superadmin":
        return True

    # 1. Direct creator of the report
    if str(report.user_id) == str(user.id):
        return True

    # 2. Access through the underlying project
    if getattr(report, "project_id", None):
        proj_res = await db.execute(select(Project).where(Project.id == report.project_id))
        project = proj_res.scalars().first()
        if project and await has_project_access(project, user, db):
            return True

    return False
