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
    if not b_name or b_name.startswith("TestBrand") or b_name == "Acme Corp":
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

# Also get from projects
c.execute("SELECT title, brand_kit, competitor_details FROM projects")
for title, bk_raw, cd_raw in c.fetchall():
    # Identify if EMAAR or Apis India or Cog Culture
    b_match = None
    for k in brands:
        if k in title.lower():
            b_match = k
            break
    if not b_match:
        # Check brand kit
        if "emaar" in title.lower():
            b_match = "emaar india"
        elif "apis" in title.lower():
            b_match = "apis india"
            
    if b_match and b_match in brands:
        if bk_raw:
            try:
                bkj = json.loads(bk_raw)
                if bkj.get("logo_url") and not brands[b_match]["logo_url"]:
                    brands[b_match]["logo_url"] = bkj.get("logo_url")
            except:
                pass
        if cd_raw:
            try:
                cds = json.loads(cd_raw)
                for cd in cds:
                    cn = cd.get("brand_name") or cd.get("name")
                    cu = cd.get("website_url") or cd.get("url")
                    cl = cd.get("logo_url")
                    if cn:
                        ck = cn.strip().lower()
                        if ck not in brands[b_match]["competitors"]:
                            brands[b_match]["competitors"][ck] = {
                                "name": cn.strip(),
                                "website": cu or "",
                                "logo_url": cl or ""
                            }
                        elif cl and not brands[b_match]["competitors"][ck]["logo_url"]:
                            brands[b_match]["competitors"][ck]["logo_url"] = cl
            except:
                pass

with open("backend/scripts/final_logos.json", "w") as f:
    json.dump(brands, f, indent=2)

print(f"Dumped {len(brands)} brands with their competitors to final_logos.json")
