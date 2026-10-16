import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models.brand import BrandConfig

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BrandConfig).where(BrandConfig.brand_name == 'tata'))
        c = result.scalars().first()
        if c:
            with open("scratch/tata_db_metrics.txt", "w", encoding="utf-8") as f:
                f.write(f"ID: {c.id}\n")
                f.write(f"Name: {c.brand_name}\n")
                f.write(f"Website URL: {c.website_url}\n")
                f.write(f"Social Metrics:\n{c.social_metrics}\n")
            print("Successfully written to scratch/tata_db_metrics.txt")
        else:
            print("Brand tata not found")

if __name__ == "__main__":
    asyncio.run(check())
