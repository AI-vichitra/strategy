import asyncio
import json
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, "D:/Strat AI")
from backend.main import app
from backend.database import async_session
from sqlalchemy import text

async def check_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Check static file endpoint
        res = await ac.get("/static/uploads/logos/8e62aaa22f8448bb9ec05d116d934a0f.png")
        print("Static test (hnm logo):", res.status_code, len(res.content))
        
        # Check projects in DB directly
        async with async_session() as session:
            r = await session.execute(text("SELECT id, title, brand_config_id, brand_kit, competitor_details FROM projects"))
            projs = r.fetchall()
            print(f"\n--- Total projects: {len(projs)} ---")
            
            # Check brand_configs
            b_res = await session.execute(text("SELECT id, brand_name, logo_url FROM brand_configs"))
            for bid, bname, bl in b_res.fetchall():
                if bl and bl.startswith("/static/"):
                    disk = os.path.join("backend", bl.lstrip("/"))
                    if not os.path.exists(disk):
                        print(f"❌ 404 BrandConfig {bname}: {bl}")
                elif not bl:
                    print(f"⚪ BrandConfig {bname}: No logo_url")

            for p in projs:
                pid, title, bc_id, bk, comp_details = p
                bkj = json.loads(bk) if bk else {}
                cdj = json.loads(comp_details) if comp_details else []
                logo = bkj.get("logo_url")
                
                # Check if logo is valid
                if logo and logo.startswith("/static/"):
                    disk = os.path.join("backend", logo.lstrip("/"))
                    if not os.path.exists(disk):
                        print(f"❌ 404 Project {pid} ({title[:30]}): {logo} MISSING ON DISK")
                elif not logo:
                    print(f"⚪ Project {pid} ({title[:30]}): No logo in brand_kit")

                for cd in cdj:
                    cl = cd.get("logo_url")
                    cn = cd.get("brand_name") or cd.get("name")
                    if cl and cl.startswith("/static/"):
                        disk = os.path.join("backend", cl.lstrip("/"))
                        if not os.path.exists(disk):
                            print(f"   ❌ 404 Comp {cn} in {title[:20]}: {cl} MISSING ON DISK")
                    elif not cl:
                        print(f"   ⚪ Comp {cn} in {title[:20]}: No logo_url")

asyncio.run(check_api())
