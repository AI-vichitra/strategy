import os
import sys
import json
import sqlite3
import httpx
from urllib.parse import urlparse

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import logo_scraper_service
from services.logo_scraper_service import scrape_and_save_logo, get_google_fallback_logo_url, _save_image_bytes

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

static_logos_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "logos")
os.makedirs(static_logos_dir, exist_ok=True)

def verify_or_scrape_logo(url: str, name: str, existing_logo: str = None) -> str:
    """Verifies existing logo file or scrapes a new one, persisting to disk."""
    if existing_logo and existing_logo.startswith("/static/uploads/logos/"):
        filename = os.path.basename(existing_logo)
        disk_path = os.path.join(static_logos_dir, filename)
        if os.path.exists(disk_path) and os.path.getsize(disk_path) > 100:
            return existing_logo

    if not url or not url.strip():
        return ""

    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"

    print(f"Scraping logo for [{name}] ({clean_url})...")
    scraped = scrape_and_save_logo(clean_url, name)
    if scraped and scraped.startswith("/static/"):
        return scraped

    # If scrape_and_save_logo returned google fallback URL or None, let's download the google fallback directly to disk
    fallback_url = get_google_fallback_logo_url(clean_url)
    if fallback_url:
        try:
            with httpx.Client(follow_redirects=True, timeout=6.0) as client:
                res = client.get(fallback_url)
                if res.status_code == 200 and len(res.content) > 100:
                    saved = _save_image_bytes(res.content, content_type=res.headers.get("content-type", "image/png"), source_url=fallback_url)
                    if saved:
                        print(f"  Downloaded Google favicon for [{name}] -> {saved}")
                        return saved
        except Exception as e:
            print(f"  Failed downloading Google favicon for {name}: {e}")

    return fallback_url or ""

# Cache to avoid re-scraping duplicate URLs
url_to_logo = {}

def get_logo_cached(url: str, name: str, existing_logo: str = None) -> str:
    if not url:
        return ""
    norm_url = url.strip().rstrip("/").lower()
    if norm_url in url_to_logo and url_to_logo[norm_url]:
        return url_to_logo[norm_url]
    
    logo = verify_or_scrape_logo(url, name, existing_logo)
    if logo:
        url_to_logo[norm_url] = logo
    return logo

print("=== STEP 1: PROCESSING BRAND_CONFIGS ===")
c.execute("SELECT id, brand_name, website_url, logo_url, competitors FROM brand_configs")
brand_configs = c.fetchall()

for bc in brand_configs:
    bc_id, b_name, web, logo, comps = bc
    print(f"\nProcessing BrandConfig #{bc_id}: {b_name} ({web})")
    
    brand_logo = get_logo_cached(web, b_name, logo)
    
    # Process competitors
    updated_comps = []
    if comps:
        try:
            parsed_comps = json.loads(comps)
            for comp in parsed_comps:
                c_name = comp.get("name") or comp.get("brand_name") or ""
                c_url = comp.get("url") or comp.get("website_url") or ""
                c_logo = comp.get("logo_url")
                
                final_c_logo = get_logo_cached(c_url, c_name, c_logo)
                comp["logo_url"] = final_c_logo
                updated_comps.append(comp)
        except Exception as e:
            print(f"  Error parsing competitors for BC #{bc_id}: {e}")
            
    # Update brand_config in db
    new_comps_json = json.dumps(updated_comps) if updated_comps else comps
    c.execute(
        "UPDATE brand_configs SET logo_url = ?, competitors = ? WHERE id = ?",
        (brand_logo, new_comps_json, bc_id)
    )

conn.commit()

print("\n=== STEP 2: PROCESSING PROJECTS ===")
c.execute("SELECT id, title, brand_kit, competitor_details, brand_config_id FROM projects")
projects = c.fetchall()

for p in projects:
    pid, title, bk, comp_details, bc_id = p
    
    # Get associated brand_config if any
    bc_logo = None
    if bc_id:
        c.execute("SELECT logo_url FROM brand_configs WHERE id = ?", (bc_id,))
        bc_row = c.fetchone()
        if bc_row:
            bc_logo = bc_row[0]

    # Parse and update brand_kit
    bkj = {}
    if bk:
        try:
            bkj = json.loads(bk)
        except Exception:
            bkj = {}
            
    current_logo = bkj.get("logo_url") or bc_logo
    if current_logo:
        bkj["logo_url"] = current_logo
    new_bk_json = json.dumps(bkj) if bkj else bk

    # Parse and update competitor_details
    updated_cd = []
    if comp_details:
        try:
            cds = json.loads(comp_details)
            for cd in cds:
                c_name = cd.get("brand_name") or cd.get("name") or ""
                c_url = cd.get("website_url") or cd.get("url") or ""
                c_logo = cd.get("logo_url")
                
                final_c_logo = get_logo_cached(c_url, c_name, c_logo)
                cd["logo_url"] = final_c_logo
                updated_cd.append(cd)
        except Exception as e:
            print(f"  Error parsing competitor_details for project {pid}: {e}")
            
    new_cd_json = json.dumps(updated_cd) if updated_cd else comp_details
    c.execute(
        "UPDATE projects SET brand_kit = ?, competitor_details = ? WHERE id = ?",
        (new_bk_json, new_cd_json, pid)
    )

conn.commit()
print("\nAll brand_configs and projects updated with logo URLs successfully!")
