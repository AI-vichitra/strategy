"""
One-off migration: adds the extracted_palette TEXT column to reports.
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
        cur = conn.execute("PRAGMA table_info(reports)")
        columns = [row[1] for row in cur.fetchall()]
        if "extracted_palette" in columns:
            print("extracted_palette column already exists on reports — nothing to do.")
            return
        conn.execute("ALTER TABLE reports ADD COLUMN extracted_palette TEXT")
        conn.commit()
        print("Added extracted_palette column to reports.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
