import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.brand import BrandConfig
from backend.models.project import Project
from backend.models.message import Message
from backend.models.report import Report

async def dry_run():
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        print(f"Total Users: {len(users)}")

        # 1. Analyze duplicate brands
        print("\n" + "=" * 60)
        print("PART 1: DUPLICATE BRANDS TO MERGE")
        print("=" * 60)
        total_dup_brands = 0
        for u in users:
            b_res = await db.execute(select(BrandConfig).where(BrandConfig.user_id == u.id))
            brands = b_res.scalars().all()
            by_norm_name = defaultdict(list)
            for b in brands:
                norm = b.brand_name.strip().lower()
                by_norm_name[norm].append(b)

            for norm_name, blist in by_norm_name.items():
                if len(blist) > 1:
                    total_dup_brands += len(blist) - 1
                    print(f"\nUser: {u.email} | Brand Name: '{norm_name}' ({len(blist)} copies)")
                    # Sort so primary is the one with projects or logo
                    blist.sort(key=lambda b: (
                        1 if b.logo_url else 0,
                    ), reverse=True)
                    primary = blist[0]
                    secondaries = blist[1:]
                    print(f"  -> PRIMARY: {primary.id} (Name='{primary.brand_name}', Logo={bool(primary.logo_url)})")
                    for s in secondaries:
                        print(f"  -> WILL MERGE & DELETE: {s.id} (Name='{s.brand_name}')")

        print(f"\nTotal duplicate brands to remove: {total_dup_brands}")

        # 2. Analyze duplicate projects
        print("\n" + "=" * 60)
        print("PART 2: DUPLICATE PROJECTS & CHATS TO MERGE")
        print("=" * 60)
        total_dup_projects = 0
        total_messages_to_merge = 0

        for u in users:
            p_res = await db.execute(
                select(Project)
                .options(selectinload(Project.messages), selectinload(Project.reports))
                .where(Project.user_id == u.id)
            )
            projects = p_res.scalars().all()

            # Group projects by (brand_config_id, agent_type_normalized)
            # or if title is identical
            by_brand_agent = defaultdict(list)
            for p in projects:
                agent_norm = (p.agent_type or "stratai").strip().lower()
                title_norm = (p.title or "").strip().lower()
                key = (p.brand_config_id, agent_norm)
                by_brand_agent[key].append(p)

            for (bid, agent), plist in by_brand_agent.items():
                if len(plist) > 1:
                    total_dup_projects += len(plist) - 1
                    # Sort: project with most messages first
                    plist.sort(key=lambda p: (len(p.messages), len(p.reports)), reverse=True)
                    primary = plist[0]
                    secondaries = plist[1:]
                    print(f"\nUser: {u.email} | Brand ID: {bid} | Agent: {agent} ({len(plist)} duplicates)")
                    print(f"  -> PRIMARY PROJECT: {primary.id} | Title='{primary.title}' | Msgs={len(primary.messages)} | Reports={len(primary.reports)}")

                    primary_msg_signatures = {
                        (m.role, m.content.strip()) for m in primary.messages
                    }
                    for s in secondaries:
                        unique_msgs = [m for m in s.messages if (m.role, m.content.strip()) not in primary_msg_signatures]
                        total_messages_to_merge += len(unique_msgs)
                        print(f"  -> WILL MERGE INTO PRIMARY & DELETE: {s.id} | Title='{s.title}' | Total Msgs={len(s.messages)} (Unique to keep: {len(unique_msgs)}) | Reports={len(s.reports)}")

        print(f"\nTotal duplicate projects to remove: {total_dup_projects}")
        print(f"Total unique messages to merge into primary projects: {total_messages_to_merge}")

if __name__ == "__main__":
    asyncio.run(dry_run())
