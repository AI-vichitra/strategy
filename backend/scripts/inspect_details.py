import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.brand import BrandConfig
from backend.models.project import Project
from backend.models.message import Message
from backend.models.report import Report

async def inspect_details():
    async with SessionLocal() as db:
        geo = (await db.execute(select(User).where(User.email == "geo@cogculture.agency"))).scalars().first()
        if not geo:
            print("geo user not found")
            return

        print(f"User: {geo.email} ({geo.id})")
        brands = (await db.execute(select(BrandConfig).where(BrandConfig.user_id == geo.id))).scalars().all()
        for b in brands:
            print(f"\n--- Brand: '{b.brand_name}' ({b.id}) ---")
            projs_res = await db.execute(
                select(Project)
                .options(selectinload(Project.messages), selectinload(Project.reports))
                .where(Project.brand_config_id == b.id)
            )
            projs = projs_res.scalars().all()
            print(f"  Total Projects: {len(projs)}")
            for p in projs:
                print(f"    Project ID: {p.id} | Title: '{p.title}' | Agent: '{p.agent_type}' | Msgs: {len(p.messages)} | Reports: {len(p.reports)}")
                for m in p.messages:
                    print(f"       Msg [{m.role}] ({m.created_at}): {m.content[:60]}...")

if __name__ == "__main__":
    asyncio.run(inspect_details())
