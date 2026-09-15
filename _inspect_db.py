import sqlite3

conn = sqlite3.connect(r'D:\database\bhavdatabase\Nse_Mainbhavdata.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in cur.fetchall()]

print("=== TABLES ===")
for name in tables:
    cur.execute(f"SELECT COUNT(*) FROM [{name}]")
    count = cur.fetchone()[0]
    cur.execute(f"PRAGMA table_info([{name}])")
    cols = [c[1] for c in cur.fetchall()]
    print(f"\n{name}  ({count} rows)")
    print(f"  cols: {cols}")

conn.close()
