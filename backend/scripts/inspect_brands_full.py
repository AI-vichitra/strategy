import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.future import select
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.brand import BrandConfig
from backend.models.project import Project

async def check_brand_details():
    async with SessionLocal() as db:
        res = await db.execute(select(BrandConfig))
        brands = res.scalars().all()
        for b in brands:
            projs_res = await db.execute(select(Project).where(Project.brand_config_id == b.id))
            projs = projs_res.scalars().all()
            print(f"Brand: ID={b.id} | User={b.user_id} | Name='{b.brand_name}' | URL={b.website_url} | Logo={b.logo_url} | HasKB={b.kb_json is not None} | Projs={len(projs)}")

if __name__ == "__main__":
    asyncio.run(check_brand_details())
