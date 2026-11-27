import os
import sys
import json
import sqlite3
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.logo_scraper_service import scrape_and_save_logo, get_google_fallback_logo_url

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
conn = sqlite3.connect(db_path, timeout=30.0)
c = conn.cursor()

# Enable WAL for better concurrency & durability
c.execute("PRAGMA journal_mode=WAL;")
c.execute("PRAGMA synchronous=NORMAL;")
conn.commit()

# Build mapping of domain/url -> logo_url
c.execute("SELECT brand_name, website_url, logo_url, competitors FROM brand_configs")
all_bcs = c.fetchall()

# Gather all brands and competitors
entities = {} # (name, url): existing_logo

for row in all_bcs:
    b_name, web, logo, comps = row
    if web:
        entities[(b_name, web)] = logo
    if comps:
        try:
            cds = json.loads(comps)
            for cd in cds:
                cn = cd.get("name") or cd.get("brand_name")
                cu = cd.get("url") or cd.get("website_url")
                cl = cd.get("logo_url")
                if cu:
                    entities[(cn, cu)] = cl
        except:
            pass

# Also from projects
c.execute("SELECT competitor_details, brand_kit FROM projects")
for cd_raw, bk_raw in c.fetchall():
    if cd_raw:
        try:
            cds = json.loads(cd_raw)
            for cd in cds:
                cn = cd.get("brand_name") or cd.get("name")
                cu = cd.get("website_url") or cd.get("url")
                cl = cd.get("logo_url")
                if cu:
                    entities[(cn, cu)] = cl
        except:
            pass

print(f"Total unique (name, url) entities: {len(entities)}")

# Resolve logos
resolved_logos = {} # clean_url -> logo_url

for (name, url), existing_logo in entities.items():
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"
    
    # Check if existing logo is valid on disk
    if existing_logo and existing_logo.startswith("/static/uploads/logos/"):
        fname = os.path.basename(existing_logo)
        fpath = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "logos", fname)
        if os.path.exists(fpath) and os.path.getsize(fpath) > 100:
            resolved_logos[clean_url] = existing_logo
            continue
            
    # Try scrape & save
    print(f"Resolving logo for {name} ({clean_url})...")
    scraped = scrape_and_save_logo(clean_url, name or "")
    if scraped:
        resolved_logos[clean_url] = scraped
    else:
        fallback = get_google_fallback_logo_url(clean_url)
        resolved_logos[clean_url] = fallback

# Update brand_configs
c.execute("SELECT id, brand_name, website_url, logo_url, competitors FROM brand_configs")
for row in c.fetchall():
    bc_id, b_name, web, logo, comps = row
    clean_web = web.strip() if web else ""
    if clean_web and not clean_web.startswith("http://") and not clean_web.startswith("https://"):
        clean_web = f"https://{clean_web}"
    
    new_logo = resolved_logos.get(clean_web, logo)
    
    new_comps = []
    if comps:
        try:
            cds = json.loads(comps)
            for cd in cds:
                cu = cd.get("url") or cd.get("website_url") or ""
                clean_cu = cu.strip()
                if clean_cu and not clean_cu.startswith("http://") and not clean_cu.startswith("https://"):
                    clean_cu = f"https://{clean_cu}"
                c_logo = resolved_logos.get(clean_cu, cd.get("logo_url"))
                cd["logo_url"] = c_logo
                new_comps.append(cd)
        except Exception as e:
            print("Error parsing comps:", e)
    
    c.execute(
        "UPDATE brand_configs SET logo_url = ?, competitors = ? WHERE id = ?",
        (new_logo, json.dumps(new_comps) if new_comps else comps, bc_id)
    )

conn.commit()

# Update projects
c.execute("SELECT id, brand_kit, competitor_details FROM projects")
for pid, bk_raw, cd_raw in c.fetchall():
    bkj = json.loads(bk_raw) if bk_raw else {}
    cdj = json.loads(cd_raw) if cd_raw else []
    
    # Update competitor_details
    updated_cds = []
    for cd in cdj:
        cu = cd.get("website_url") or cd.get("url") or ""
        clean_cu = cu.strip()
        if clean_cu and not clean_cu.startswith("http://") and not clean_cu.startswith("https://"):
            clean_cu = f"https://{clean_cu}"
        c_logo = resolved_logos.get(clean_cu, cd.get("logo_url"))
        cd["logo_url"] = c_logo
        updated_cds.append(cd)
        
    c.execute(
        "UPDATE projects SET competitor_details = ? WHERE id = ?",
        (json.dumps(updated_cds) if updated_cds else cd_raw, pid)
    )

conn.commit()

c.execute("PRAGMA integrity_check;")
print("Database integrity check:", c.fetchall())

conn.close()
print("All logos successfully resolved and populated into database!")
