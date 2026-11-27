import sqlite3
import json
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
    SELECT p.id, p.title, p.brand_config_id, p.questionnaire_answers, p.brand_kit, bc.brand_name, bc.website_url, bc.logo_url
    FROM projects p
    LEFT JOIN brand_configs bc ON p.brand_config_id = bc.id
""")

for row in c.fetchall():
    pid, title, bc_id, qa, bk, bc_name, bc_web, bc_logo = row
    brand_name = bc_name
    website = bc_web
    
    if qa:
        try:
            qaj = json.loads(qa)
            # check if brand name or website in questionnaire
            if not brand_name and qaj.get("brand_name"):
                brand_name = qaj.get("brand_name")
            if not website and qaj.get("website_url"):
                website = qaj.get("website_url")
        except:
            pass
            
    logo = None
    if bk:
        try:
            bkj = json.loads(bk)
            logo = bkj.get("logo_url")
        except:
            pass
            
    print(f"Project ID: {pid}")
    print(f"  Title      : {title}")
    print(f"  Brand Name : {brand_name}")
    print(f"  Website    : {website}")
    print(f"  Logo URL   : {logo}")
