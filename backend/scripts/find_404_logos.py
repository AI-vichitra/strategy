import sqlite3
import os
import json

conn = sqlite3.connect("backend/stratai.db")
c = conn.cursor()

print("=== CHECKING BRAND_CONFIGS ===")
c.execute("SELECT id, brand_name, website_url, logo_url, competitors FROM brand_configs")
for row in c.fetchall():
    bid, bname, web, logo, comps = row
    if logo:
        if logo.startswith("/static/"):
            fpath = os.path.join("backend", logo.lstrip("/"))
            exists = os.path.exists(fpath)
            sz = os.path.getsize(fpath) if exists else 0
            if not exists:
                print(f"❌ 404 BRAND LOGO: {bname} -> {logo} (MISSING ON DISK)")
            else:
                print(f"✅ BRAND LOGO: {bname} -> {logo} ({sz} bytes)")
        else:
            print(f"🌐 EXTERNAL BRAND LOGO: {bname} -> {logo}")
    else:
        print(f"⚠️ NO LOGO: {bname}")

    if comps:
        try:
            cds = json.loads(comps)
            for cd in cds:
                cname = cd.get("name") or cd.get("brand_name")
                clogo = cd.get("logo_url")
                if clogo:
                    if clogo.startswith("/static/"):
                        fpath = os.path.join("backend", clogo.lstrip("/"))
                        exists = os.path.exists(fpath)
                        sz = os.path.getsize(fpath) if exists else 0
                        if not exists:
                            print(f"   ❌ 404 COMP LOGO: {cname} (under {bname}) -> {clogo} (MISSING ON DISK)")
                        else:
                            pass # valid
                    else:
                        print(f"   🌐 EXTERNAL COMP LOGO: {cname} -> {clogo}")
                else:
                    print(f"   ⚠️ NO LOGO: {cname} (under {bname})")
        except Exception as e:
            pass

print("\n=== CHECKING PROJECTS ===")
c.execute("SELECT id, title, brand_kit, competitor_details FROM projects")
for row in c.fetchall():
    pid, title, bk_raw, cd_raw = row
    if bk_raw:
        try:
            bk = json.loads(bk_raw)
            plogo = bk.get("logo_url")
            if plogo and plogo.startswith("/static/"):
                fpath = os.path.join("backend", plogo.lstrip("/"))
                if not os.path.exists(fpath):
                    print(f"❌ 404 PROJECT LOGO: {title} ({pid}) -> {plogo}")
        except:
            pass
    if cd_raw:
        try:
            cds = json.loads(cd_raw)
            for cd in cds:
                clogo = cd.get("logo_url")
                cname = cd.get("brand_name") or cd.get("name")
                if clogo and clogo.startswith("/static/"):
                    fpath = os.path.join("backend", clogo.lstrip("/"))
                    if not os.path.exists(fpath):
                        print(f"   ❌ 404 PROJECT COMP: {cname} in '{title[:30]}' -> {clogo}")
        except:
            pass
