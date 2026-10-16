import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models.brand import BrandConfig
from backend.models.project import Project

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BrandConfig))
        configs = result.scalars().all()
        print(f"Total BrandConfigs in DB: {len(configs)}")
        for c in configs:
            print("========================================")
            print(f"BrandConfig ID: {c.id}")
            print(f"Name: {c.brand_name}")
            print(f"Website URL: {c.website_url}")
            comp_str = str(c.competitors).encode('ascii', 'ignore').decode('ascii')
            print(f"Competitors: {comp_str[:100]}")
            metrics_len = len(c.social_metrics) if c.social_metrics else 0
            print(f"Social Metrics Length: {metrics_len}")
            print("========================================")

        proj_result = await session.execute(select(Project))
        projects = proj_result.scalars().all()
        print(f"\nTotal Projects in DB: {len(projects)}")
        for p in projects:
            print("========================================")
            print(f"Project ID: {p.id}")
            print(f"Title: {p.title}")
            print(f"Agent Type: {p.agent_type}")
            print(f"BrandConfig ID: {p.brand_config_id}")
            print("========================================")

if __name__ == "__main__":
    asyncio.run(check())
