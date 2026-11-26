import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.project import Project
from backend.models.brand import BrandConfig
from backend.models.message import Message
from backend.models.report import Report

async def inspect_geo():
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            projs_res = await db.execute(
                select(Project)
                .options(selectinload(Project.messages), selectinload(Project.reports))
                .where(Project.user_id == u.id)
                .order_by(Project.created_at.desc())
            )
            projs = projs_res.scalars().all()
            if projs:
                print(f"\n=======================================================")
                print(f"USER: {u.email} ({u.id}) - Total Projects: {len(projs)}")
                print(f"=======================================================")
                for p in projs:
                    brand_res = await db.execute(select(BrandConfig).where(BrandConfig.id == p.brand_config_id))
                    brand = brand_res.scalars().first()
                    brand_name = brand.brand_name if brand else p.brand_config_id
                    print(f"  Project: {p.id}")
                    print(f"    Title: {p.title}")
                    print(f"    Agent: {p.agent_type}")
                    print(f"    Brand: {brand_name}")
                    print(f"    Team: {p.team_id}")
                    print(f"    Messages: {len(p.messages)}")
                    print(f"    Reports: {len(p.reports)}")
                    print(f"    Created: {p.created_at}")

if __name__ == "__main__":
    asyncio.run(inspect_geo())
