"""
End-to-End Test Suite for Teams & Shared Chat Logic in StratAI
Tests team creation, member invitation, token resolution, registration with invite token,
team-scoped project visibility, access control (collaborative vs forbidden), and member removal.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime

# Ensure root directory is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from sqlalchemy.future import select
from backend.database import engine, Base, SessionLocal
from backend.models.user import User
from backend.models.team import Team, TeamMember, PendingInvitation
from backend.models.project import Project
from backend.models.message import Message
from backend.models.brand import BrandConfig
from backend.main import _add_missing_columns
from backend.utils.permissions import has_project_access, get_user_team_ids, has_team_admin_access
from backend.utils.token import generate_reset_token, hash_token
from backend.schemas.team import TeamCreate, InviteMemberRequest, AcceptInviteRequest
from backend.schemas.user import UserCreate
from backend.schemas.project import ProjectCreate
from backend.routers import teams, auth, projects


async def run_tests():
    print("=" * 65)
    print("STARTING STRATAI TEAMS & SHARED CHAT END-TO-END TEST SUITE")
    print("=" * 65)

    # 1. Database schema migration & initialization
    print("\n[TEST 1] Verifying database schema & tables exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _add_missing_columns()
    print("✓ Database tables (teams, team_members, pending_invitations) and columns ready.")

    async with SessionLocal() as db:
        # 2. Setup Test Users
        print("\n[TEST 2] Setting up test users (Admin A, Unregistered Member B, Outsider C)...")
        admin_email = f"admin_{uuid.uuid4().hex[:6]}@agency.com"
        outsider_email = f"outsider_{uuid.uuid4().hex[:6]}@random.com"
        member_email = f"member_{uuid.uuid4().hex[:6]}@agency.com"

        # Create Admin User
        admin_user = await auth.register(
            user=UserCreate(email=admin_email, password="Password123!", full_name="Admin Alice"),
            db=db
        )
        assert admin_user.role == "admin"
        print(f"✓ Created Admin A: {admin_user.email} (ID: {admin_user.id})")

        # Create Outsider User
        outsider_user = await auth.register(
            user=UserCreate(email=outsider_email, password="Password123!", full_name="Outsider Bob"),
            db=db
        )
        print(f"✓ Created Outsider C: {outsider_user.email} (ID: {outsider_user.id})")

        # Create BrandConfig for testing
        brand_id = str(uuid.uuid4())
        brand = BrandConfig(
            id=brand_id,
            user_id=admin_user.id,
            brand_name="Acme Corp",
            category="SaaS",
            pipeline_status="complete",
        )
        db.add(brand)
        await db.commit()
        print(f"✓ Created Test Brand: Acme Corp (ID: {brand_id})")

        # 3. Create a Team Workspace
        print("\n[TEST 3] Creating a Team Workspace...")
        from fastapi import BackgroundTasks
        bg = BackgroundTasks()
        team_resp = await teams.create_team(
            payload=TeamCreate(name="Acme Growth Squad", description="Marketing & Strategy"),
            background_tasks=bg,
            db=db,
            current_user=admin_user
        )
        team_id = team_resp.id
        assert team_resp.name == "Acme Growth Squad"
        assert team_resp.is_admin is True
        assert team_resp.role == "admin"
        assert team_resp.members_count == 1
        print(f"✓ Team created: '{team_resp.name}' (ID: {team_id}) with Admin Alice as owner.")

        # 4. Verify Admin has team admin access
        is_admin = await has_team_admin_access(team_id, admin_user, db)
        assert is_admin is True, "Admin should have team admin access"
        is_outsider_admin = await has_team_admin_access(team_id, outsider_user, db)
        assert is_outsider_admin is False, "Outsider should not have team admin access"
        print("✓ Team admin permissions verified.")

        # 5. Invite New (Unregistered) Member via Email
        print("\n[TEST 4] Inviting new member B to team...")
        from fastapi import BackgroundTasks
        bg = BackgroundTasks()
        from unittest.mock import MagicMock
        req_mock = MagicMock()

        invite_res = await teams.invite_member(
            payload=InviteMemberRequest(email=member_email, role="member"),
            background_tasks=bg,
            request=req_mock,
            team_id=team_id,
            db=db,
            current_user=admin_user
        )
        assert invite_res["status"] == "success"
        assert invite_res["already_registered"] is False
        print(f"✓ Invitation dispatched to: {member_email}")

        # Check pending invitation row
        inv_check = await db.execute(
            select(PendingInvitation).where(PendingInvitation.team_id == team_id, PendingInvitation.status == "pending")
        )
        inv_record = inv_check.scalars().first()
        assert inv_record is not None
        assert inv_record.email == member_email
        print(f"✓ PendingInvitation stored in DB with hashed token.")

        # 6. Test Public Resolve Invite Endpoint
        print("\n[TEST 5] Resolving invitation token via public endpoint...")
        # Find raw token: we can test by creating a known token or resolving
        test_raw_token = generate_reset_token()
        inv_record.invite_token = hash_token(test_raw_token)
        await db.commit()

        resolved = await teams.resolve_invitation(token=test_raw_token, db=db)
        assert resolved.email == member_email
        assert resolved.team_name == "Acme Growth Squad"
        assert resolved.valid is True
        assert resolved.user_exists is False
        print(f"✓ Public resolve returned correct email '{resolved.email}' (user_exists={resolved.user_exists}) for team '{resolved.team_name}'.")

        # Verify check-email before registration
        chk_pre = await auth.check_email(email=member_email, db=db)
        assert chk_pre["exists"] is False

        # 7. Member B Registers with the Invite Token
        print("\n[TEST 6] Member B registers using the invite token...")
        member_user = await auth.register(
            user=UserCreate(
                email=member_email,
                password="MemberPassword123!",
                full_name="Member Charlie",
                invite_token=test_raw_token
            ),
            db=db
        )
        assert member_user.role == "member"
        assert member_user.parent_user_id == admin_user.id
        print(f"✓ Member B registered: {member_user.email} (Role: {member_user.role}, Parent: {member_user.parent_user_id})")

        # Verify Member B was automatically added to TeamMember
        mem_check = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == member_user.id)
        )
        tm_record = mem_check.scalars().first()
        assert tm_record is not None
        assert tm_record.role == "member"
        print(f"✓ Member B is automatically an active member of Team '{team_resp.name}'.")

        # 8. Check Team Details (Members list)
        print("\n[TEST 7] Fetching team details & members list...")
        team_details = await teams.get_team_details(team_id=team_id, db=db, current_user=member_user)
        assert team_details.members_count == 2
        member_emails = [m.email for m in team_details.members]
        assert admin_email in member_emails
        assert member_email in member_emails
        print(f"✓ Team details verified: {team_details.members_count} active members ({', '.join(member_emails)}).")

        # 9. Create a Team-Shared Chat Project
        print("\n[TEST 8] Admin A creates a project assigned to the team...")
        proj_res = await projects.create_project(
            project=ProjectCreate(
                brand_config_id=brand_id,
                agent_type="competitor_intelligence",
                title="Q4 SaaS Rivalry Intelligence",
                team_id=team_id
            ),
            db=db,
            current_user=admin_user
        )
        project_id = proj_res.id
        assert proj_res.team_id == team_id
        # Add a message to simulate active chat
        db.add(Message(project_id=project_id, role="user", content="Analyze our competitors"))
        await db.commit()
        print(f"✓ Team project created: '{proj_res.title}' (ID: {project_id}, Team: {proj_res.team_id})")

        # 10. Access Control Checks for Live Shared Chat
        print("\n[TEST 9] Verifying collaborative access permissions...")
        proj_orm_res = await db.execute(select(Project).where(Project.id == project_id))
        proj_orm = proj_orm_res.scalars().first()

        # Admin A (owner) should have access
        can_admin_access = await has_project_access(proj_orm, admin_user, db)
        assert can_admin_access is True, "Admin owner must have access"
        print("✓ Admin A has full project access.")

        # Member B (team member) should have access!
        can_member_access = await has_project_access(proj_orm, member_user, db)
        assert can_member_access is True, "Team member B must have access to team project"
        print("✓ Team Member B has access to shared team project.")

        # Outsider C (not in team) must NOT have access!
        can_outsider_access = await has_project_access(proj_orm, outsider_user, db)
        assert can_outsider_access is False, "Outsider C must NOT have access"
        print("✓ Outsider C access correctly DENIED (403 forbidden).")

        # 11. Member B lists projects via GET /api/projects
        print("\n[TEST 10] Testing project listing for team members...")
        member_projects = await projects.get_projects(team_id=None, db=db, current_user=member_user)
        member_project_ids = [p.id for p in member_projects]
        assert project_id in member_project_ids, "Member B must see the team project in their workspace feed"
        print(f"✓ Member B workspace feed lists the team project: '{member_projects[0].title}'.")

        # Outsider C lists projects -> should see 0
        outsider_projects = await projects.get_projects(team_id=None, db=db, current_user=outsider_user)
        assert len(outsider_projects) == 0
        print("✓ Outsider C workspace feed correctly contains 0 projects.")

        # 12. Move a personal project to team
        print("\n[TEST 11] Testing assigning an existing personal project to team...")
        personal_proj = await projects.create_project(
            project=ProjectCreate(
                brand_config_id=brand_id,
                agent_type="paid_ads",
                title="Private Google Ads Draft",
            ),
            db=db,
            current_user=admin_user
        )
        assert personal_proj.team_id is None
        # Assign to team
        assign_res = await teams.assign_project_to_team(
            team_id=team_id,
            project_id=personal_proj.id,
            db=db,
            current_user=admin_user
        )
        assert assign_res["status"] == "success"
        # Refresh and check
        updated_proj_res = await db.execute(select(Project).where(Project.id == personal_proj.id))
        updated_proj = updated_proj_res.scalars().first()
        assert updated_proj.team_id == team_id
        assert await has_project_access(updated_proj, member_user, db) is True
        print(f"✓ Personal project successfully migrated to team and now accessible by Member B.")

        # 13. Remove Member B from Team
        print("\n[TEST 12] Removing Member B from team and verifying revocation...")
        await teams.remove_team_member(team_id=team_id, user_id=member_user.id, db=db, current_user=admin_user)
        # Verify access revoked
        revoked_access = await has_project_access(proj_orm, member_user, db)
        assert revoked_access is False, "Member B should no longer have access after removal"
        print("✓ Member B successfully removed and project access instantly revoked.")

        print("\n" + "=" * 65)
        print("ALL 12 TESTS PASSED SUCCESSFULLY! TEAMS & SHARED CHAT WORKING!")
        print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_tests())
