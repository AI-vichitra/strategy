import sqlite3
import os
from datetime import datetime

db_path = os.path.join('backend', 'stratai.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

now = datetime.utcnow().isoformat()

for table in ['projects', 'brand_configs', 'messages', 'users']:
    try:
        c.execute(f"UPDATE {table} SET created_at = ? WHERE created_at IS NULL", (now,))
        print(f'Updated {c.rowcount} rows in {table}')
    except Exception as e:
        print(f'Error updating {table}: {e}')

conn.commit()
conn.close()
