import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.future import select
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.brand import BrandConfig
from backend.models.project import Project

async def check_brands():
    async with SessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            b_res = await db.execute(select(BrandConfig).where(BrandConfig.user_id == u.id))
            brands = b_res.scalars().all()
            if brands:
                print(f"=== Brands for {u.email} ({u.id}) ===")
                for b in brands:
                    print(f"  Brand ID: {b.id} | Name: '{b.brand_name}' | Slug: '{b.brand_slug}' | Team: {b.team_id}")

if __name__ == "__main__":
    asyncio.run(check_brands())
