import os
import sys
import json
import sqlite3
import httpx
from urllib.parse import urlparse

sys.path.insert(0, "D:/Strat AI")
from backend.services.logo_scraper_service import _save_image_bytes

conn = sqlite3.connect("backend/stratai.db")
c = conn.cursor()

def download_and_save_external(url: str) -> str:
    if not url or not url.startswith("http"):
        return url
    try:
        with httpx.Client(follow_redirects=True, timeout=8.0) as client:
            res = client.get(url)
            if res.status_code == 200 and len(res.content) > 50:
                saved = _save_image_bytes(res.content, content_type=res.headers.get("content-type", "image/png"), source_url=url)
                if saved:
                    print(f"Downloaded {url} -> {saved}")
                    return saved
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return url

# Fix the two broken Cog Culture projects
cog_logo = "/static/uploads/logos/cad1ea4b9bb44eddbb110a2f80c43582.png"
for broken_pid in ["cfe6884e-098f-4de5-8d58-40a227781309", "57d432ea-e0fa-4bb2-bdc4-b2341f74de29"]:
    c.execute("SELECT brand_kit FROM projects WHERE id = ?", (broken_pid,))
    row = c.fetchone()
    if row and row[0]:
        bk = json.loads(row[0])
        bk["logo_url"] = cog_logo
        c.execute("UPDATE projects SET brand_kit = ? WHERE id = ?", (json.dumps(bk), broken_pid))
        print(f"Fixed project {broken_pid} logo_url -> {cog_logo}")

# Scan brand_configs and download any external logos
c.execute("SELECT id, logo_url, competitors FROM brand_configs")
for bc_id, logo, comps in c.fetchall():
    new_logo = logo
    if logo and logo.startswith("http"):
        new_logo = download_and_save_external(logo)
    
    new_comps = []
    if comps:
        try:
            cds = json.loads(comps)
            for cd in cds:
                cl = cd.get("logo_url")
                if cl and cl.startswith("http"):
                    cd["logo_url"] = download_and_save_external(cl)
                new_comps.append(cd)
        except Exception as e:
            pass
            
    c.execute("UPDATE brand_configs SET logo_url = ?, competitors = ? WHERE id = ?", (new_logo, json.dumps(new_comps) if new_comps else comps, bc_id))

# Scan projects and download any external logos
c.execute("SELECT id, brand_kit, competitor_details FROM projects")
for pid, bk_raw, cd_raw in c.fetchall():
    new_bk = bk_raw
    if bk_raw:
        try:
            bk = json.loads(bk_raw)
            if bk.get("logo_url") and bk["logo_url"].startswith("http"):
                bk["logo_url"] = download_and_save_external(bk["logo_url"])
                new_bk = json.dumps(bk)
        except:
            pass
            
    new_cd = cd_raw
    if cd_raw:
        try:
            cds = json.loads(cd_raw)
            for cd in cds:
                cl = cd.get("logo_url")
                if cl and cl.startswith("http"):
                    cd["logo_url"] = download_and_save_external(cl)
            new_cd = json.dumps(cds)
        except:
            pass
            
    c.execute("UPDATE projects SET brand_kit = ?, competitor_details = ? WHERE id = ?", (new_bk, new_cd, pid))

conn.commit()
print("All external logos downloaded and localized successfully!")
conn.close()
