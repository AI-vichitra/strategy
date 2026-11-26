import sqlite3
import json
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get all brand_configs
c.execute("""
    SELECT id, brand_name, website_url, logo_url, competitors, category
    FROM brand_configs
    ORDER BY id ASC
""")
brand_configs = c.fetchall()

# Get all projects
c.execute("""
    SELECT p.id, p.title, p.brand_config_id, p.brand_kit, p.competitor_details, 
           (p.logo_data IS NOT NULL) as has_blob, p.logo_mime, bc.brand_name as bc_brand_name, bc.website_url as bc_web
    FROM projects p
    LEFT JOIN brand_configs bc ON p.brand_config_id = bc.id
    ORDER BY p.id ASC
""")
projects = c.fetchall()

print("==================================================================")
print(f"DATABASE SUMMARY: {len(brand_configs)} brand_configs, {len(projects)} projects")
print("==================================================================")

brands_data = {}

# Process brand_configs
for bc in brand_configs:
    bc_id, b_name, web, logo, comps, cat = bc
    b_name_clean = b_name.strip() if b_name else f"BrandConfig #{bc_id}"
    
    parsed_comps = []
    if comps:
        try:
            parsed_comps = json.loads(comps)
        except Exception:
            pass
            
    key = b_name_clean.lower()
    if key not in brands_data:
        brands_data[key] = {
            "name": b_name_clean,
            "website": web or "",
            "logo_url": logo,
            "category": cat or "",
            "competitors": {},
            "source": ["brand_config"]
        }
    else:
        if not brands_data[key]["website"] and web:
            brands_data[key]["website"] = web
        if not brands_data[key]["logo_url"] and logo:
            brands_data[key]["logo_url"] = logo
        if "brand_config" not in brands_data[key]["source"]:
            brands_data[key]["source"].append("brand_config")

    for comp in parsed_comps:
        c_name = comp.get("name") or comp.get("brand_name")
        if c_name:
            c_key = c_name.strip().lower()
            if c_key not in brands_data[key]["competitors"]:
                brands_data[key]["competitors"][c_key] = {
                    "name": c_name.strip(),
                    "website": comp.get("url") or comp.get("website_url") or "",
                    "logo_url": comp.get("logo_url")
                }
            else:
                existing = brands_data[key]["competitors"][c_key]
                if not existing["website"] and (comp.get("url") or comp.get("website_url")):
                    existing["website"] = comp.get("url") or comp.get("website_url")
                if not existing["logo_url"] and comp.get("logo_url"):
                    existing["logo_url"] = comp.get("logo_url")

# Process projects
for p in projects:
    p_id, title, bc_id, bk, comp_details, has_blob, mime, bc_name, bc_web = p
    
    brand_logo = None
    if bk:
        try:
            bkj = json.loads(bk)
            brand_logo = bkj.get("logo_url")
        except Exception:
            pass

    # Brand name resolution
    b_name = bc_name or title
    key = b_name.strip().lower()
    
    if key not in brands_data:
        brands_data[key] = {
            "name": b_name.strip(),
            "website": bc_web or "",
            "logo_url": brand_logo,
            "category": "",
            "competitors": {},
            "source": ["project"]
        }
    else:
        if brand_logo and not brands_data[key]["logo_url"]:
            brands_data[key]["logo_url"] = brand_logo
        if "project" not in brands_data[key]["source"]:
            brands_data[key]["source"].append("project")

    # Competitors from project
    if comp_details:
        try:
            cds = json.loads(comp_details)
            for cd in cds:
                c_name = cd.get("brand_name") or cd.get("name")
                if c_name:
                    c_key = c_name.strip().lower()
                    if c_key not in brands_data[key]["competitors"]:
                        brands_data[key]["competitors"][c_key] = {
                            "name": c_name.strip(),
                            "website": cd.get("website_url") or cd.get("url") or "",
                            "logo_url": cd.get("logo_url")
                        }
                    else:
                        existing = brands_data[key]["competitors"][c_key]
                        if not existing["website"] and (cd.get("website_url") or cd.get("url")):
                            existing["website"] = cd.get("website_url") or cd.get("url")
                        if not existing["logo_url"] and cd.get("logo_url"):
                            existing["logo_url"] = cd.get("logo_url")
        except Exception:
            pass

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")

# Print consolidated view
all_competitors_global = {}

for b_key, b_info in sorted(brands_data.items()):
    # Check logo on disk
    logo = b_info["logo_url"]
    file_exists = False
    if logo and logo.startswith("/static/"):
        rel_path = logo.lstrip("/").replace("/", os.sep)
        full_path = os.path.join(os.path.dirname(__file__), "..", rel_path)
        file_exists = os.path.exists(full_path)
    
    print(f"\n========================================================")
    print(f"BRAND: {b_info['name']}")
    print(f"  Website  : {b_info['website']}")
    print(f"  Logo URL : {logo} (Local file exists: {file_exists})")
    print(f"  Sources  : {b_info['source']}")
    print(f"  Competitors count: {len(b_info['competitors'])}")
    
    for c_key, c_info in sorted(b_info["competitors"].items()):
        clogo = c_info["logo_url"]
        c_file_exists = False
        if clogo and clogo.startswith("/static/"):
            rel_path = clogo.lstrip("/").replace("/", os.sep)
            full_path = os.path.join(os.path.dirname(__file__), "..", rel_path)
            c_file_exists = os.path.exists(full_path)
        print(f"    - Competitor: {c_info['name']}")
        print(f"        Website : {c_info['website']}")
        print(f"        Logo    : {clogo} (Exists: {c_file_exists})")
        
        if c_key not in all_competitors_global:
            all_competitors_global[c_key] = c_info
            all_competitors_global[c_key]["for_brands"] = [b_info["name"]]
        else:
            all_competitors_global[c_key]["for_brands"].append(b_info["name"])
            if not all_competitors_global[c_key]["logo_url"] and clogo:
                all_competitors_global[c_key]["logo_url"] = clogo

print("\n\n========================================================")
print(f"TOTAL DISTINCT BRANDS: {len(brands_data)}")
print(f"TOTAL DISTINCT COMPETITORS: {len(all_competitors_global)}")
print("========================================================")
