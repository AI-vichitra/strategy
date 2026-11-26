import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from collections import defaultdict
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.project import Project
from backend.models.brand import BrandConfig

async def analyze_duplicates():
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        user_map = {u.id: u.email for u in users}
        brands = (await db.execute(select(BrandConfig))).scalars().all()
        brand_map = {b.id: b.brand_name for b in brands}

        res = await db.execute(select(Project).options(selectinload(Project.messages)))
        projs = res.scalars().all()

        # Group by (user_id, brand_config_id, title)
        by_user_brand_title = defaultdict(list)
        for p in projs:
            by_user_brand_title[(p.user_id, p.brand_config_id, p.title.strip().lower())].append(p)

        print("=== DUPLICATE GROUPS BY (user, brand, title) ===")
        dup_count = 0
        for (uid, bid, title), plist in by_user_brand_title.items():
            if len(plist) > 1:
                dup_count += 1
                user_email = user_map.get(uid, uid)
                brand_name = brand_map.get(bid, bid)
                print(f'\nDuplicate Group #{dup_count}: User={user_email}, Brand={brand_name}, Title="{title}"')
                for p in plist:
                    print(f'   - ID: {p.id} | Agent: {p.agent_type} | Msgs: {len(p.messages)} | Created: {p.created_at}')

        print("\n=== DUPLICATE GROUPS BY (user_id, brand_config_id, agent_type) ===")
        by_user_brand_agent = defaultdict(list)
        for p in projs:
            by_user_brand_agent[(p.user_id, p.brand_config_id, (p.agent_type or "").strip().lower())].append(p)

        dup_agent_count = 0
        for (uid, bid, agent), plist in by_user_brand_agent.items():
            if len(plist) > 1:
                dup_agent_count += 1
                user_email = user_map.get(uid, uid)
                brand_name = brand_map.get(bid, bid)
                print(f'\nDuplicate Agent Group #{dup_agent_count}: User={user_email}, Brand={brand_name}, Agent="{agent}"')
                for p in plist:
                    print(f'   - ID: {p.id} | Title: "{p.title}" | Msgs: {len(p.messages)} | Created: {p.created_at}')

if __name__ == "__main__":
    asyncio.run(analyze_duplicates())
