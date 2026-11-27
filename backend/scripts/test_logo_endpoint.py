import asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, "D:/Strat AI")
from backend.main import app
from backend.database import async_session
from sqlalchemy import text

async def test_logo_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with async_session() as session:
            r = await session.execute(text("SELECT id, title, brand_kit FROM projects"))
            projs = r.fetchall()
            
            success_count = 0
            for pid, title, bk in projs:
                res = await ac.get(f"/api/projects/{pid}/logo")
                if res.status_code == 200:
                    success_count += 1
                else:
                    print(f"Project logo {pid} ({title[:30]}): status {res.status_code}")
            
            print(f"\nTested {len(projs)} projects: {success_count} returned 200 OK from /api/projects/{{id}}/logo")

asyncio.run(test_logo_endpoints())
