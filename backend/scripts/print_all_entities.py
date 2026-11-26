import sqlite3
import json
import os

conn = sqlite3.connect("backend/stratai.db")
c = conn.cursor()

c.execute("SELECT brand_name, website_url, logo_url, competitors FROM brand_configs WHERE brand_name NOT LIKE 'TestBrand%' AND brand_name != 'Acme Corp' ORDER BY brand_name ASC")
rows = c.fetchall()

seen = set()
brands = []

for bname, web, logo, comps in rows:
    key = bname.strip().lower()
    if key in seen:
        continue
    seen.add(key)
    
    comp_list = []
    if comps:
        try:
            cds = json.loads(comps)
            for cd in cds:
                cn = cd.get("name") or cd.get("brand_name")
                cu = cd.get("url") or cd.get("website_url")
                cl = cd.get("logo_url")
                comp_list.append({"name": cn, "website": cu, "logo": cl})
        except:
            pass
            
    brands.append({
        "brand": bname.strip(),
        "website": web,
        "logo": logo,
        "competitors": comp_list
    })

# Also include EMAAR India and Apis India from projects if not present in brand_configs
c.execute("SELECT title, brand_kit, competitor_details FROM projects")
for title, bk_raw, cd_raw in c.fetchall():
    t_lower = title.lower()
    b_found = None
    if "emaar" in t_lower and "emaar india" not in seen:
        b_found = "EMAAR India"
        web = "https://in.emaar.com/en/"
        seen.add("emaar india")
    elif "apis" in t_lower and "apis india" not in seen:
        b_found = "apis india"
        web = "https://apisindia.com/en"
        seen.add("apis india")
        
    if b_found:
        bkj = json.loads(bk_raw) if bk_raw else {}
        cdj = json.loads(cd_raw) if cd_raw else []
        comp_list = []
        for cd in cdj:
            comp_list.append({
                "name": cd.get("brand_name") or cd.get("name"),
                "website": cd.get("website_url") or cd.get("url"),
                "logo": cd.get("logo_url")
            })
        brands.append({
            "brand": b_found,
            "website": web,
            "logo": bkj.get("logo_url"),
            "competitors": comp_list
        })

print(f"Total Unique Brands: {len(brands)}")
for b in brands:
    print(f"\nBrand: {b['brand']} | Web: {b['website']} | Logo: {b['logo']}")
    print(f"  Competitors ({len(b['competitors'])}):")
    for cp in b['competitors']:
        print(f"    - {cp['name']} ({cp['website']}) -> {cp['logo']}")
