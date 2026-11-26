import sqlite3
import os
import shutil

db_path = os.path.join(os.path.dirname(__file__), "..", "stratai.db")
recovered_path = os.path.join(os.path.dirname(__file__), "..", "stratai_recovered.db")
backup_path = os.path.join(os.path.dirname(__file__), "..", "stratai_corrupt_backup.db")

# Backup current db
shutil.copyfile(db_path, backup_path)
print(f"Backed up current DB to {backup_path}")

if os.path.exists(recovered_path):
    os.remove(recovered_path)

src_conn = sqlite3.connect(db_path)
dest_conn = sqlite3.connect(recovered_path)

c = src_conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [r[0] for r in c.fetchall()]
print("Tables to recover:", tables)

for t in tables:
    try:
        c.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}'")
        row = c.fetchone()
        if not row:
            continue
        create_sql = row[0]
        dest_conn.execute(create_sql)
        
        # Read rows individually using cursor to survive partial row corruption
        dest_c = dest_conn.cursor()
        c.execute(f"SELECT * FROM {t}")
        count = 0
        while True:
            try:
                r = c.fetchone()
                if r is None:
                    break
                placeholders = ", ".join(["?"] * len(r))
                dest_c.execute(f"INSERT INTO {t} VALUES ({placeholders})", r)
                count += 1
            except Exception as row_err:
                print(f"  Warning on row in {t}: {row_err}")
                continue
        dest_conn.commit()
        print(f"Recovered {t}: {count} rows")
    except Exception as e:
        print(f"Error on {t}: {e}")

src_conn.close()
dest_conn.close()

# Check recovered DB integrity
verify_conn = sqlite3.connect(recovered_path)
vc = verify_conn.cursor()
vc.execute("PRAGMA integrity_check;")
check_res = vc.fetchall()
print("Recovered DB integrity check:", check_res)
verify_conn.close()

if check_res == [('ok',)]:
    print("Integrity check passed! Replacing original db with recovered db...")
    shutil.copyfile(recovered_path, db_path)
    print("Database replaced successfully.")
else:
    print("Recovered DB integrity check failed!")
