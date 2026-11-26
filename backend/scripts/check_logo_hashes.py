import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

logos_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "logos")
files = os.listdir(logos_dir)

print(f"Checking {len(files)} files against all columns in projects and brand_configs...")

for f in files:
    stem = os.path.splitext(f)[0]
    # search in projects
    c.execute(f"SELECT id, title FROM projects WHERE brand_kit LIKE '%{stem}%' OR competitor_details LIKE '%{stem}%'")
    matches = c.fetchall()
    # search in brand_configs
    c.execute(f"SELECT id, brand_name FROM brand_configs WHERE logo_url LIKE '%{stem}%' OR competitors LIKE '%{stem}%'")
    bc_matches = c.fetchall()
    
    if matches or bc_matches:
        print(f"File {f}:")
        for m in matches:
            print(f"  Project: {m[1]} ({m[0]})")
        for bm in bc_matches:
            print(f"  BrandConfig: {bm[1]} ({bm[0]})")
