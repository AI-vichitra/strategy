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

async def run():
    async with SessionLocal() as db:
        res = await db.execute(select(User).where(User.email.in_(["geo@cogculture.agency", "naveenkumar@cogculture.agency"])))
        users = res.scalars().all()
        for u in users:
            print(f"=== {u.email} ({u.id}) ===")
            p_res = await db.execute(select(Project).options(selectinload(Project.messages), selectinload(Project.reports)).where(Project.user_id == u.id).order_by(Project.created_at.desc()))
            projs = p_res.scalars().all()
            for p in projs:
                brand_res = await db.execute(select(BrandConfig).where(BrandConfig.id == p.brand_config_id))
                b = brand_res.scalars().first()
                bname = b.brand_name if b else p.brand_config_id
                print(f"Project: {p.id} | Title: \"{p.title}\" | Agent: {p.agent_type} | Brand: {bname} | Msgs: {len(p.messages)} | Reports: {len(p.reports)} | Created: {p.created_at}")

if __name__ == "__main__":
    asyncio.run(run())
