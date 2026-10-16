import sqlite3

def dump_handles():
    conn = sqlite3.connect('backend/stratai.db')
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name, brand_handle, confirmed_competitor_handles FROM brand_configs WHERE brand_name='Google';")
    row = cursor.fetchone()
    if row:
        print(f"Brand: {row[0]}")
        print(f"Brand Handle: {row[1]}")
        print(f"Competitor Handles: {row[2]}")
    else:
        print("Google not found")

if __name__ == '__main__':
    dump_handles()
