import sqlite3
import sys

def dump_brands():
    conn = sqlite3.connect('backend/stratai.db')
    cursor = conn.cursor()
    
    print("--- BRANDS ---")
    cursor.execute("SELECT id, brand_name, website_url, category, competitors, social_metrics FROM brand_configs;")
    brands = cursor.fetchall()
    for b in brands:
        print(f"ID: {b[0]}")
        print(f"Name: {b[1]}")
        print(f"Website: {b[2]}")
        print(f"Category: {b[3]}")
        print(f"Competitors: {b[4]}")
        metrics = str(b[5]) if b[5] is not None else ""
        print(f"Social Metrics (first 200 chars): {metrics[:200].encode('ascii', 'replace').decode('ascii')}...")
        print("-" * 50)

    print("\n--- PROJECTS ---")
    cursor.execute("SELECT id, brand_config_id, agent_type, title, questionnaire_answers FROM projects;")
    projects = cursor.fetchall()
    for p in projects:
        print(f"ID: {p[0]}")
        print(f"Brand Config ID: {p[1]}")
        print(f"Agent: {p[2]}")
        print(f"Title: {p[3]}")
        print(f"QA: {p[4]}")
        print("-" * 50)

if __name__ == '__main__':
    dump_brands()
