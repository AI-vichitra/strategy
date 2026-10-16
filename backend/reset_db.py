"""
Database Reset Utility for StratAI
==================================
Clears all brand research, projects, messages, and connector credentials
while preserving user login accounts.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "stratai.db")

def reset_database(keep_users=True):
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        tables_to_clear = ["brand_configs", "projects", "messages", "connector_credentials"]
        if not keep_users:
            tables_to_clear.append("users")

        for table in tables_to_clear:
            cur.execute(f"DELETE FROM {table};")
            print(f"Cleared table: {table}")

        conn.commit()
        print("\n[SUCCESS] Database cleaned successfully!")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to clean database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_database(keep_users=True)
