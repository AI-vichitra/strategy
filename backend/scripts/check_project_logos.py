import asyncio
import json
import os
import sys

sys.path.insert(0, "D:/Strat AI")
from backend.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as session:
        r = await session.execute(text("SELECT id, title, brand_config_id, brand_kit, competitor_details, (logo_data IS NOT NULL) FROM projects"))
        projs = r.fetchall()
        print(f"Total projects: {len(projs)}")
        
        missing_bk = 0
        missing_cd = 0
        missing_file = 0
        
        for p in projs:
            pid, title, bc_id, bk, comp_details, has_blob = p
            bkj = json.loads(bk) if bk else {}
            cdj = json.loads(comp_details) if comp_details else []
            
            logo = bkj.get("logo_url")
            if not logo:
                missing_bk += 1
                print(f"Project missing brand_kit logo: {title} (ID: {pid}, BC: {bc_id})")
            elif logo.startswith("/static/"):
                disk = os.path.join("backend", logo.lstrip("/"))
                if not os.path.exists(disk):
                    missing_file += 1
                    print(f"Project brand_kit logo MISSING DISK FILE: {title} -> {logo}")
                    
            for cd in cdj:
                cl = cd.get("logo_url")
                if not cl:
                    missing_cd += 1
                elif cl.startswith("/static/"):
                    disk = os.path.join("backend", cl.lstrip("/"))
                    if not os.path.exists(disk):
                        missing_file += 1
                        print(f"Competitor {cd.get('brand_name')} logo MISSING DISK FILE: {cl}")

        print(f"\nSummary:")
        print(f"  Missing brand_kit logo: {missing_bk}")
        print(f"  Missing competitor logo: {missing_cd}")
        print(f"  Missing disk files: {missing_file}")

asyncio.run(check())
