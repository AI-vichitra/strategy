import asyncio
import aiosqlite
import os

DB_PATH = os.path.join("backend", "stratai.db")

async def migrate():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(brand_configs)")
        cols = {row[1] for row in await cursor.fetchall()}
        print("Existing columns:", cols)

        migrations = [
            ("brand_slug",                   "TEXT"),
            ("brand_handle",                 "TEXT"),
            ("confirmed_competitor_handles", "TEXT"),
            ("pipeline_status",              "TEXT DEFAULT 'pending'"),
        ]

        for col, col_type in migrations:
            if col not in cols:
                await db.execute(f"ALTER TABLE brand_configs ADD COLUMN {col} {col_type}")
                print(f"  Added: {col}")
            else:
                print(f"  Already exists: {col}")

        await db.commit()
        print("Migration complete!")

asyncio.run(migrate())
