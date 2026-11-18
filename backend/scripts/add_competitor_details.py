"""
One-off migration: adds the competitor_details TEXT column to projects.
Alembic isn't wired up in this repo, so schema changes are applied directly
against stratai.db, matching the pattern used for prior ad-hoc columns/tables.
Safe to re-run — skips the ALTER TABLE if the column already exists.
"""
import os
import sqlite3

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stratai.db")


def main():
    conn = sqlite3.connect(_DB_PATH)
    try:
        cur = conn.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cur.fetchall()]
        if "competitor_details" in columns:
            print("competitor_details column already exists on projects — nothing to do.")
            return
        conn.execute("ALTER TABLE projects ADD COLUMN competitor_details TEXT")
        conn.commit()
        print("Added competitor_details column to projects.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
