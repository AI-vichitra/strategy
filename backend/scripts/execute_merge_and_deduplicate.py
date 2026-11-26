import asyncio
import os
import sys
import shutil
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.brand import BrandConfig
from backend.models.project import Project
from backend.models.message import Message
from backend.models.report import Report
from backend.models.chat_share import ChatShare

async def merge_and_deduplicate():
    # 1. Backup DB
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "stratai.db"))
    if os.path.exists(db_path):
        backup_path = f"{db_path}.bak.{int(datetime.utcnow().timestamp())}"
        shutil.copy2(db_path, backup_path)
        print(f"✓ Backed up database to: {backup_path}")

    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()

        # -------------------------------------------------------------
        # STEP 1: Deduplicate Brands
        # -------------------------------------------------------------
        print("\n[STEP 1] Deduplicating Brands...")
        merged_brands_count = 0

        for u in users:
            b_res = await db.execute(select(BrandConfig).where(BrandConfig.user_id == u.id))
            brands = b_res.scalars().all()
            by_norm_name = defaultdict(list)
            for b in brands:
                norm = (b.brand_name or "").strip().lower()
                by_norm_name[norm].append(b)

            for norm_name, blist in by_norm_name.items():
                if len(blist) > 1:
                    # Sort: prefer brand with projects, then logo, then earliest created
                    blist_counts = []
                    for b in blist:
                        p_cnt_res = await db.execute(select(Project).where(Project.brand_config_id == b.id))
                        p_cnt = len(p_cnt_res.scalars().all())
                        blist_counts.append((p_cnt, 1 if b.logo_url else 0, b.created_at or datetime.min, b))
                    blist_counts.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

                    primary = blist_counts[0][3]
                    secondaries = [x[3] for x in blist_counts[1:]]

                    print(f"Merging {len(secondaries)} duplicate brand(s) into '{primary.brand_name}' ({primary.id}) for {u.email}...")

                    for s in secondaries:
                        # Copy missing assets if primary didn't have them
                        if not primary.logo_url and s.logo_url:
                            primary.logo_url = s.logo_url
                        if not primary.kb_json and s.kb_json:
                            primary.kb_json = s.kb_json
                        if not primary.reference_docs and s.reference_docs:
                            primary.reference_docs = s.reference_docs
                        if not primary.competitors and s.competitors:
                            primary.competitors = s.competitors

                        # Reassign projects pointing to secondary brand
                        projs_to_move = (await db.execute(select(Project).where(Project.brand_config_id == s.id))).scalars().all()
                        for p in projs_to_move:
                            p.brand_config_id = primary.id

                        await db.flush()
                        await db.delete(s)
                        merged_brands_count += 1

        await db.commit()
        print(f"✓ Successfully merged and deleted {merged_brands_count} duplicate brands.")

        # -------------------------------------------------------------
        # STEP 2: Deduplicate Projects & Merge Chats
        # -------------------------------------------------------------
        print("\n[STEP 2] Deduplicating Projects and Merging Chat Messages...")
        merged_projects_count = 0
        merged_messages_count = 0
        deleted_dup_messages_count = 0
        reparented_reports_count = 0

        for u in users:
            p_res = await db.execute(
                select(Project)
                .options(selectinload(Project.messages), selectinload(Project.reports))
                .where(Project.user_id == u.id)
            )
            projects = p_res.scalars().all()

            # Group projects by (brand_config_id, agent_type_normalized)
            by_brand_agent = defaultdict(list)
            for p in projects:
                agent_norm = (p.agent_type or "stratai").strip().lower()
                key = (p.brand_config_id, agent_norm)
                by_brand_agent[key].append(p)

            for (bid, agent), plist in by_brand_agent.items():
                if len(plist) > 1:
                    # Sort: project with most messages, then reports, then latest active
                    plist.sort(key=lambda p: (
                        len(p.messages),
                        len(p.reports),
                        p.created_at or datetime.min
                    ), reverse=True)

                    primary = plist[0]
                    secondaries = plist[1:]

                    print(f"Merging {len(secondaries)} project(s) for brand={bid}, agent={agent} into primary project {primary.id} ('{primary.title}')...")

                    # Signatures of existing messages in primary
                    primary_msg_sigs = {
                        (m.role, m.content.strip()) for m in primary.messages
                    }

                    for s in secondaries:
                        # 1. Merge messages
                        for m in list(s.messages):
                            sig = (m.role, m.content.strip())
                            if sig in primary_msg_sigs:
                                # Redundant message, delete
                                await db.delete(m)
                                deleted_dup_messages_count += 1
                            else:
                                # Unique message, re-parent to primary project
                                m.project_id = primary.id
                                primary_msg_sigs.add(sig)
                                merged_messages_count += 1

                        # 2. Re-parent reports
                        for r in list(s.reports):
                            r.project_id = primary.id
                            reparented_reports_count += 1

                        # 3. Re-parent chat shares
                        shares = (await db.execute(select(ChatShare).where(ChatShare.project_id == s.id))).scalars().all()
                        for cs in shares:
                            cs.project_id = primary.id

                        await db.flush()
                        await db.delete(s)
                        merged_projects_count += 1

        await db.commit()
        print(f"✓ Successfully merged and deleted {merged_projects_count} duplicate projects.")
        print(f"✓ Re-parented {merged_messages_count} unique messages into primary chats.")
        print(f"✓ Removed {deleted_dup_messages_count} duplicate messages.")
        print(f"✓ Re-parented {reparented_reports_count} reports.")

if __name__ == "__main__":
    asyncio.run(merge_and_deduplicate())
