import asyncio
import json
import os
import sys

sys.path.insert(0, "D:/Strat AI")
from backend.main import app
from backend.database import async_session
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport

async def check():
    async with async_session() as session:
        # Check all users
        u_res = await session.execute(text("SELECT id, email FROM users"))
        users = u_res.fetchall()
        print("Users in DB:", users)
        
        # Check brand_configs per user
        bc_res = await session.execute(text("SELECT id, user_id, brand_name, website_url, logo_url, competitors FROM brand_configs"))
        bcs = bc_res.fetchall()
        print(f"\nTotal brand_configs: {len(bcs)}")
        for b in bcs:
            bid, uid, bname, web, logo, comps = b
            print(f"Brand: {bname} | User: {uid} | Logo: {logo}")
            try:
                comps_list = json.loads(comps) if comps else []
                logos_count = sum(1 for c in comps_list if c.get("logo_url"))
                print(f"  Competitors: {len(comps_list)} total, {logos_count} have logos")
            except Exception as e:
                print(f"  Error parsing comps: {e}")

asyncio.run(check())
