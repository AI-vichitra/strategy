import asyncio
import sys
import os

# Add current dir to python path
sys.path.insert(0, os.path.abspath('.'))

from backend.database import AsyncSessionLocal
from sqlalchemy import text

async def cleanup():
    async with AsyncSessionLocal() as session:
        # Delete BrandConfigs that don't have a StratAI project
        await session.execute(text("DELETE FROM brand_configs WHERE id NOT IN (SELECT brand_config_id FROM projects WHERE agent_type = 'StratAI')"))
        
        # Delete Projects that don't have a valid BrandConfig
        await session.execute(text("DELETE FROM projects WHERE brand_config_id NOT IN (SELECT id FROM brand_configs)"))
        
        # Delete Messages that don't have a valid Project
        await session.execute(text("DELETE FROM messages WHERE project_id NOT IN (SELECT id FROM projects)"))
        
        await session.commit()
        print("Cleanup done")

if __name__ == "__main__":
    asyncio.run(cleanup())
