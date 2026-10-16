import sqlite3
import os

db_path = 'backend/stratai.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
    for row in cursor.fetchall():
        print(row[0])
        print("---")
else:
    print(f"Database {db_path} not found.")
