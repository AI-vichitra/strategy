"""
One-off migration: adds the reference_docs TEXT column to brand_configs.
Alembic isn't wired up in this repo, so schema changes are applied directly
against stratai.db, matching the pattern used for prior ad-hoc columns/tables.
Safe to re-run — skips the ALTER TABLE if the column already exists.
"""
import os
import sqlite3
import sys

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stratai.db")


def main():
    try:
        conn = sqlite3.connect(_DB_PATH)
        try:
            cur = conn.execute("PRAGMA table_info(brand_configs)")
            columns = [row[1] for row in cur.fetchall()]
            if "reference_docs" in columns:
                print("Column 'reference_docs' already exists, skipping.")
                return
            conn.execute("ALTER TABLE brand_configs ADD COLUMN reference_docs TEXT")
            conn.commit()
            print("Column 'reference_docs' added successfully.")
        finally:
            conn.close()
    except Exception as exc:
        print(f"Migration failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
