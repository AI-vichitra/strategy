import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from backend.database import AsyncSessionLocal
from backend.models.brand import BrandConfig
from backend.services.pipeline_service import run_autonomous_pipeline
from sqlalchemy.future import select

async def trigger():
    async with AsyncSessionLocal() as session:
        # Fetch Godrej and Emaar brands
        res = await session.execute(select(BrandConfig))
        brands = res.scalars().all()
        
        target_brands = brands
        
        if not target_brands:
            print("No brands found in the database.")
            return
            
        for brand in target_brands:
            print(f"\n[TRIGGER] Rerunning pipeline for: {brand.brand_name} (ID: {brand.id})")
            try:
                await run_autonomous_pipeline(
                    brand_config_id=brand.id,
                    brand_name=brand.brand_name,
                    website_url=brand.website_url,
                    category=brand.category
                )
                print(f"[TRIGGER] Finished pipeline successfully for {brand.brand_name}")
            except Exception as e:
                print(f"[TRIGGER] Failed pipeline for {brand.brand_name}: {e}")

if __name__ == "__main__":
    asyncio.run(trigger())
