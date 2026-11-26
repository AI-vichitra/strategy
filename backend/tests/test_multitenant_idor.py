"""
Comprehensive Multi-Tenant Isolation & IDOR Security Test Suite
Tests strict cross-tenant isolation, IDOR prevention, and role-based permissions
across teams, projects, reports, sections, brands, reference docs, and chats.
"""
import asyncio
import os
import sys
import uuid
import json
from datetime import datetime

# Ensure root directory is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.future import select
from backend.database import engine, Base, SessionLocal
from backend.models.user import User
from backend.models.team import Team, TeamMember
from backend.models.project import Project
from backend.models.brand import BrandConfig
from backend.models.report import Report
from backend.models.message import Message
from backend.main import _add_missing_columns
from backend.utils.permissions import (
    has_project_access,
    has_project_admin_access,
    has_brand_access,
    has_brand_admin_access,
    has_report_access,
    has_team_admin_access,
    get_user_team_ids,
)
from backend.schemas.user import UserCreate
from backend.schemas.project import ProjectCreate, ProjectUpdate
from backend.schemas.brand import ReferenceDocAdd
from backend.schemas.team import TeamCreate, MemberProjectsUpdateRequest
from backend.schemas.chat import ChatRequest, ChatMessage
from backend.routers.chat_share import CreateShareRequest
from backend.routers import auth, projects, reports, report_sections, brand, teams, chat, chat_share


async def run_idor_security_tests():
    print("=" * 70)
    print("STARTING STRATAI MULTI-TENANT ISOLATION & IDOR SECURITY TEST SUITE")
    print("=" * 70)

    # 1. DB Init
    print("\n[STEP 1] Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _add_missing_columns()
    print("✓ Database ready.")

    async with SessionLocal() as db:
        # 2. Setup Tenants
        # Tenant 1: Admin Alice & Member Bob
        # Tenant 2: Admin Eve (Attacker/Outsider)
        print("\n[STEP 2] Setting up Tenant 1 (Alice & Bob) and Tenant 2 (Eve - Outsider)...")
        t1_admin_email = f"alice_{uuid.uuid4().hex[:6]}@tenant1.com"
        t1_member_email = f"bob_{uuid.uuid4().hex[:6]}@tenant1.com"
        t2_admin_email = f"eve_{uuid.uuid4().hex[:6]}@tenant2.com"

        alice = await auth.register(user=UserCreate(email=t1_admin_email, password="Password123!", full_name="Alice Admin"), db=db)
        eve = await auth.register(user=UserCreate(email=t2_admin_email, password="Password123!", full_name="Eve Attacker"), db=db)
        bob = await auth.register(
            user=UserCreate(email=t1_member_email, password="Password123!", full_name="Bob Member", role="member", parent_user_id=alice.id),
            db=db
        )
        print(f"✓ Tenant 1 Admin: {alice.email} ({alice.id})")
        print(f"✓ Tenant 1 Member: {bob.email} ({bob.id})")
        print(f"✓ Tenant 2 Attacker: {eve.email} ({eve.id})")

        # 3. Tenant 1 creates a Team, Brand, Project, and Report
        print("\n[STEP 3] Tenant 1 (Alice) creates Team 'Apex Growth', Brand 'Apex Corp', and Projects...")
        team_t1 = await teams.create_team(
            payload=TeamCreate(name="Apex Growth", description="Tenant 1 confidential team"),
            background_tasks=BackgroundTasks(),
            db=db,
            current_user=alice,
        )
        # Link Bob as member
        bob_mem = TeamMember(
            id=str(uuid.uuid4()),
            team_id=team_t1.id,
            user_id=bob.id,
            role="member",
            allowed_projects=None,
        )
        db.add(bob_mem)
        await db.commit()

        # Create Brand for Tenant 1
        brand_t1 = BrandConfig(
            id=str(uuid.uuid4()),
            brand_name="Apex Corp",
            brand_slug="apex-corp",
            category="Fintech",
            target_market="North America",
            user_id=alice.id,
            team_id=team_t1.id,
            reference_docs=json.dumps([{"ref_id": "ref_101", "filename": "q4_financials.pdf", "text": "Confidential Q4 Net Profit $50M"}]),
        )
        db.add(brand_t1)
        await db.commit()
        await db.refresh(brand_t1)

        # Create Shared Team Project 1
        proj_shared = await projects.create_project(
            project=ProjectCreate(
                title="Apex Global Market Entry",
                agent_type="StratAI",
                brand_config_id=brand_t1.id,
                team_id=team_t1.id,
            ),
            db=db,
            current_user=alice,
        )
        db.add(Message(id=str(uuid.uuid4()), project_id=proj_shared.id, role="user", content="Analyze Apex market entry"))
        await db.commit()
        # Create Private Personal Project 2 (Alice personal, NOT shared with team)
        proj_private = await projects.create_project(
            project=ProjectCreate(
                title="Alice Personal Confidential Strategy",
                agent_type="StratAI",
                brand_config_id=brand_t1.id,
                team_id=None,
            ),
            db=db,
            current_user=alice,
        )
        # Create Report Snapshot for Shared Project
        report_t1 = Report(
            id=str(uuid.uuid4()),
            project_id=proj_shared.id,
            user_id=alice.id,
            agent_type="StratAI",
            title="Apex Q4 Confidential Report",
            content="# Confidential Strategy\nDo not share outside Apex.",
            version=1,
            chart_count=1,
        )
        db.add(report_t1)
        await db.commit()
        await db.refresh(report_t1)
        print("✓ Created Tenant 1 resources: Team, Brand, Shared Project, Private Project, and Report.")

        # =========================================================================
        # SECURITY TEST 4: IDOR Attacks on Project Endpoints by Tenant 2 (Eve)
        # =========================================================================
        print("\n[TEST 4] Testing IDOR prevention on Project endpoints (Eve -> Alice's projects)...")

        # 4a. Eve attempts to read Alice's project
        try:
            await projects.get_project(project_id=proj_shared.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve accessed Alice's project!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/projects/{proj_shared.id} -> 403 Forbidden")

        # 4b. Eve attempts to update Alice's project
        try:
            await projects.update_project(
                project_id=proj_shared.id,
                project_update=ProjectUpdate(title="Hacked Title"),
                db=db,
                current_user=eve
            )
            assert False, "IDOR VULNERABILITY: Eve modified Alice's project!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve PUT /api/projects/{proj_shared.id} -> 403 Forbidden")

        # 4c. Eve attempts to read Alice's project details & reference docs
        try:
            await projects.get_project_details(project_id=proj_shared.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve viewed Alice's project details!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/projects/{proj_shared.id}/details -> 403 Forbidden")

        # 4d. Eve attempts to view reports list for Alice's project
        try:
            await projects.get_project_reports(project_id=proj_shared.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve viewed reports list for Alice's project!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/projects/{proj_shared.id}/reports -> 403 Forbidden")

        # 4e. Eve attempts to tamper with reference docs on Alice's project
        try:
            await projects.add_reference_doc(
                project_id=proj_shared.id,
                payload=ReferenceDocAdd(ref_id="evil_ref", filename="malware.pdf"),
                db=db,
                current_user=eve
            )
            assert False, "IDOR VULNERABILITY: Eve injected a reference doc into Alice's project!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve PUT /api/projects/{proj_shared.id}/reference-docs -> 403 Forbidden")

        # 4f. Eve attempts to delete Alice's project
        try:
            await projects.delete_project(project_id=proj_shared.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve deleted Alice's project!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve DELETE /api/projects/{proj_shared.id} -> 403 Forbidden")

        # =========================================================================
        # SECURITY TEST 5: IDOR Attacks on Report & Export Endpoints by Tenant 2 (Eve)
        # =========================================================================
        print("\n[TEST 5] Testing IDOR prevention on Report & Export endpoints (Eve -> Alice's reports)...")

        # 5a. Eve attempts to view report
        try:
            await reports.get_report(report_id=report_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve viewed Alice's report!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/reports/{report_t1.id} -> 403 Forbidden")

        # 5b. Eve attempts to export report as DOCX
        try:
            await reports.export_report_docx(report_id=report_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve exported Alice's report DOCX!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/reports/{report_t1.id}/export/docx -> 403 Forbidden")

        # 5c. Eve attempts to export report as PPTX
        try:
            await reports.export_report_pptx(report_id=report_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve exported Alice's report PPTX!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/reports/{report_t1.id}/export/pptx -> 403 Forbidden")

        # 5d. Eve attempts to export report as PDF
        try:
            await reports.export_report_pdf(report_id=report_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve exported Alice's report PDF!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/reports/{report_t1.id}/export/pdf -> 403 Forbidden")

        # 5e. Eve attempts to view or edit report sections
        try:
            await report_sections.get_sections(report_id=report_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve accessed Alice's report sections!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/reports/{report_t1.id}/sections -> 403 Forbidden")

        # =========================================================================
        # SECURITY TEST 6: IDOR Attacks on Brand Endpoints by Tenant 2 (Eve)
        # =========================================================================
        print("\n[TEST 6] Testing IDOR prevention on Brand endpoints (Eve -> Alice's brand)...")

        # 6a. Eve attempts to modify Alice's brand
        try:
            await brand.update_brand(brand_id=brand_t1.id, payload={"brand_name": "Eve Brand"}, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve modified Alice's brand!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve PUT /api/brands/{brand_t1.id} -> 403 Forbidden")

        # 6b. Eve attempts to delete Alice's brand
        try:
            await brand.delete_brand(brand_id=brand_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve deleted Alice's brand!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve DELETE /api/brands/{brand_t1.id} -> 403 Forbidden")

        # 6c. Eve attempts to attach her own project to Alice's brand (cross-tenant project injection)
        try:
            await projects.create_project(
                project=ProjectCreate(title="Eve Injected Project", agent_type="StratAI", brand_config_id=brand_t1.id),
                db=db,
                current_user=eve,
            )
            assert False, "IDOR VULNERABILITY: Eve attached project to Alice's brand!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve POST /api/projects/ with Alice's brand_config_id -> 403 Forbidden")

        # =========================================================================
        # SECURITY TEST 7: IDOR Attacks on Team Workspace Endpoints by Tenant 2 (Eve)
        # =========================================================================
        print("\n[TEST 7] Testing IDOR prevention on Team Workspace endpoints (Eve -> Alice's team)...")

        # 7a. Eve attempts to view Alice's team workspace
        try:
            await teams.get_team_details(team_id=team_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve accessed Alice's team details!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/teams/{team_t1.id} -> 403 Forbidden")

        # 7b. Eve attempts to view projects in Alice's team workspace
        try:
            await teams.get_team_projects(team_id=team_t1.id, db=db, current_user=eve)
            assert False, "IDOR VULNERABILITY: Eve listed projects in Alice's team!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve GET /api/teams/{team_t1.id}/projects -> 403 Forbidden")

        # 7c. Eve attempts to invite people into Alice's team
        try:
            from backend.schemas.team import InviteMemberRequest
            await teams.invite_member(
                payload=InviteMemberRequest(email="spy@hacker.com", team_id=team_t1.id),
                background_tasks=BackgroundTasks(),
                request=None,
                team_id=team_t1.id,
                db=db,
                current_user=eve
            )
            assert False, "IDOR VULNERABILITY: Eve invited member to Alice's team!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve POST /api/teams/{team_t1.id}/invite -> 403 Forbidden")

        # =========================================================================
        # SECURITY TEST 8: Chat & Share IDOR Protection
        # =========================================================================
        print("\n[TEST 8] Testing IDOR prevention on Chat Streaming & Chat Share...")

        # 8a. Eve attempts to trigger AI chat on Alice's project
        try:
            await chat.chat_stream(
                req=ChatRequest(project_id=proj_shared.id, messages=[ChatMessage(role="user", content="Steal data")]),
                db=db,
                current_user=eve
            )
            assert False, "IDOR VULNERABILITY: Eve streamed chat on Alice's project!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve POST /api/chat/ on Alice's project -> 403 Forbidden")

        # 8b. Eve attempts to create a chat share link on Alice's project
        try:
            from backend.routers.chat_share import CreateShareRequest
            await chat_share.create_or_update_share(
                payload=CreateShareRequest(project_id=proj_shared.id),
                background_tasks=BackgroundTasks(),
                db=db,
                current_user=eve
            )
            assert False, "IDOR VULNERABILITY: Eve shared Alice's project!"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"✓ Blocked Eve POST /api/chat/share on Alice's project -> 403 Forbidden")

        # =========================================================================
        # SECURITY TEST 9: Intra-Team Member Permissions & Scope Isolation
        # =========================================================================
        print("\n[TEST 9] Testing Intra-Team Permissions (Bob Member vs Alice Admin)...")

        # 9a. Bob (Team Member) CAN access the shared project
        assert await has_project_access(proj_shared, bob, db) is True
        shared_view = await projects.get_project(project_id=proj_shared.id, db=db, current_user=bob)
        assert shared_view.id == proj_shared.id
        print("✓ Bob (Team Member) can access shared project 'Apex Global Market Entry'")

        # 9b. Bob (Team Member) CAN access the report on the shared project
        assert await has_report_access(report_t1, bob, db) is True
        report_view = await reports.get_report(report_id=report_t1.id, db=db, current_user=bob)
        assert report_view.id == report_t1.id
        print("✓ Bob (Team Member) can view report on shared project")

        # 9c. Bob (Team Member) CANNOT delete the shared project (Only Admin/Creator can delete)
        try:
            await projects.delete_project(project_id=proj_shared.id, db=db, current_user=bob)
            assert False, "PERMISSION ESCALATION: Regular member Bob deleted shared project!"
        except HTTPException as e:
            assert e.status_code == 403
            print("✓ Blocked Bob DELETE /api/projects/ on shared team project -> 403 Forbidden (Admin only)")

        # 9d. Bob (Team Member) CANNOT access Alice's private personal project (proj_private)
        # Even though they are in the same team, private projects stay private!
        assert await has_project_access(proj_private, bob, db) is False
        try:
            await projects.get_project(project_id=proj_private.id, db=db, current_user=bob)
            assert False, "PRIVACY LEAK: Bob accessed Alice's unshared personal project!"
        except HTTPException as e:
            assert e.status_code == 403
            print("✓ Blocked Bob from Alice's private unshared personal project -> 403 Forbidden")

        # 9e. Scoped Member Restrictions: Restrict Bob to project X only, verify project Y is blocked
        proj_shared_y = await projects.create_project(
            project=ProjectCreate(
                title="Apex Confidential Acquisition Strategy",
                agent_type="StratAI",
                brand_config_id=brand_t1.id,
                team_id=team_t1.id,
            ),
            db=db,
            current_user=alice,
        )
        # Restrict Bob's allowed_projects strictly to proj_shared.id (excluding proj_shared_y)
        bob_mem_row = (await db.execute(select(TeamMember).where(TeamMember.id == bob_mem.id))).scalar_one()
        bob_mem_row.allowed_projects = [proj_shared.id]
        await db.commit()

        # Bob can still access proj_shared
        assert await has_project_access(proj_shared, bob, db) is True
        # Bob CANNOT access proj_shared_y
        assert await has_project_access(proj_shared_y, bob, db) is False
        try:
            await projects.get_project(project_id=proj_shared_y.id, db=db, current_user=bob)
            assert False, "SCOPED ACCESS FAILED: Bob accessed restricted project Y!"
        except HTTPException as e:
            assert e.status_code == 403
            print("✓ Scoped project isolation verified: Bob restricted from unassigned project Y -> 403 Forbidden")

        print("\n" + "=" * 70)
        print("ALL MULTI-TENANT ISOLATION & IDOR SECURITY TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_idor_security_tests())
