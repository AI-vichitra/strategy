import os
import sys
import json
import sqlite3

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, brand_name, website_url, logo_url, competitors FROM brand_configs ORDER BY brand_name ASC")
bcs = c.fetchall()

brands = {}

for bc in bcs:
    bc_id, b_name, web, logo, comps = bc
    if not b_name or b_name.startswith("TestBrand"):
        continue
    
    b_key = b_name.strip().lower()
    if b_key not in brands:
        brands[b_key] = {
            "name": b_name.strip(),
            "website": web or "",
            "logo_url": logo or "",
            "competitors": {}
        }
    else:
        if logo and not brands[b_key]["logo_url"]:
            brands[b_key]["logo_url"] = logo
        if web and not brands[b_key]["website"]:
            brands[b_key]["website"] = web

    if comps:
        try:
            parsed = json.loads(comps)
            for cp in parsed:
                cname = cp.get("name") or cp.get("brand_name")
                cweb = cp.get("url") or cp.get("website_url")
                clogo = cp.get("logo_url")
                if cname:
                    ckey = cname.strip().lower()
                    if ckey not in brands[b_key]["competitors"]:
                        brands[b_key]["competitors"][ckey] = {
                            "name": cname.strip(),
                            "website": cweb or "",
                            "logo_url": clogo or ""
                        }
                    else:
                        if clogo and not brands[b_key]["competitors"][ckey]["logo_url"]:
                            brands[b_key]["competitors"][ckey]["logo_url"] = clogo
        except:
            pass

# Also check projects for additional brands / competitors
c.execute("SELECT title, brand_kit, competitor_details, brand_config_id FROM projects")
projects = c.fetchall()
for p in projects:
    title, bk, comp_details, bc_id = p
    if comp_details:
        try:
            cds = json.loads(comp_details)
            # Find matching brand
            matched_b = None
            for b_key in brands:
                if b_key in title.lower():
                    matched_b = b_key
                    break
            if matched_b:
                for cd in cds:
                    cname = cd.get("brand_name") or cd.get("name")
                    cweb = cd.get("website_url") or cd.get("url")
                    clogo = cd.get("logo_url")
                    if cname:
                        ckey = cname.strip().lower()
                        if ckey not in brands[matched_b]["competitors"]:
                            brands[matched_b]["competitors"][ckey] = {
                                "name": cname.strip(),
                                "website": cweb or "",
                                "logo_url": clogo or ""
                            }
                        elif clogo and not brands[matched_b]["competitors"][ckey]["logo_url"]:
                            brands[matched_b]["competitors"][ckey]["logo_url"] = clogo
        except:
            pass

print(json.dumps(brands, indent=2))
