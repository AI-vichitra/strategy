import sqlite3
import json
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("==================================================")
print("             BRAND CONFIGS IN DATABASE            ")
print("==================================================")
c.execute("SELECT brand_name, website_url, logo_url, competitors FROM brand_configs")
for row in c.fetchall():
    b_name, web, logo, comps = row
    print(f"\nBrand Name: {b_name}")
    print(f"  Website : {web}")
    print(f"  Logo URL: {logo}")
    if comps:
        try:
            parsed = json.loads(comps)
            print(f"  Competitors ({len(parsed)}):")
            for comp in parsed:
                print(f"    - Name: {comp.get('name')} | URL: {comp.get('url')} | Logo: {comp.get('logo_url')}")
        except Exception as e:
            print(f"  Competitors (raw): {comps}")

print("\n==================================================")
print("             PROJECTS IN DATABASE                 ")
print("==================================================")
c.execute("SELECT id, title, brand_kit, competitor_details, (logo_data IS NOT NULL), logo_mime FROM projects")
for row in c.fetchall():
    pid, title, bk, comp_details, has_blob, mime = row
    print(f"\nProject: {title} (ID: {pid})")
    print(f"  Has logo_data blob: {has_blob} (Mime: {mime})")
    if bk:
        try:
            bkj = json.loads(bk)
            print(f"  Brand Kit Logo URL : {bkj.get('logo_url')}")
            print(f"  Brand Kit Colors   : {bkj.get('colors')}")
        except Exception as e:
            print(f"  Brand Kit (raw): {bk}")
    if comp_details:
        try:
            cdj = json.loads(comp_details)
            print(f"  Competitor Details ({len(cdj)}):")
            for cd in cdj:
                print(f"    - Name: {cd.get('brand_name')} | Web: {cd.get('website_url')} | Logo: {cd.get('logo_url')}")
        except Exception as e:
            print(f"  Competitor Details (raw): {comp_details}")

print("\n==================================================")
print("             FILES IN STATIC/UPLOADS/LOGOS        ")
print("==================================================")
logos_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "logos")
if os.path.exists(logos_dir):
    files = os.listdir(logos_dir)
    print(f"Total files in {logos_dir}: {len(files)}")
    for f in sorted(files):
        sz = os.path.getsize(os.path.join(logos_dir, f))
        print(f"  - {f} ({sz} bytes)")
else:
    print(f"Directory {logos_dir} does not exist.")
