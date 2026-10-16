import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models.brand import BrandConfig

async def fix():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BrandConfig).where(BrandConfig.brand_name == 'tata'))
        c = result.scalars().first()
        if c:
            c.website_url = "https://www.tata.com/"
            await session.commit()
            print("Successfully corrected Tata website URL to https://www.tata.com/")
        else:
            print("Brand tata not found")

if __name__ == "__main__":
    asyncio.run(fix())
