"""
Creates data/Nse_data.db by copying selected tables from the source DB.

Table mapping (source → new name):
  bhavdata_master_tb  → bhav_tb        (last 60 trading dates)
  splitdata_tb        → split_tb       (all 345 rows)
  shareregistry_tb    → master_tb      (all rows, core columns only)
  msidchange_tb       → rename_tb      (all rows)
  master_wdate_tb     → wmaster_tb     (all rows, pipeline-relevant flags only)
"""

import sqlite3
import os

SRC_DB  = r"D:\database\bhavdatabase\Nse_Mainbhavdata.db"
DST_DIR = r"D:\Stock_Ai_Predictor\data"
DST_DB  = os.path.join(DST_DIR, "Nse_data.db")

os.makedirs(DST_DIR, exist_ok=True)

# Remove existing destination DB so we start clean
if os.path.exists(DST_DB):
    os.remove(DST_DB)
    print(f"Removed existing {DST_DB}")

src = sqlite3.connect(SRC_DB)
dst = sqlite3.connect(DST_DB)
dst.execute("PRAGMA journal_mode = WAL;")
dst.execute("PRAGMA synchronous = NORMAL;")

print(f"Source : {SRC_DB}")
print(f"Target : {DST_DB}")
print()


# ─── Helper ────────────────────────────────────────────────────────────────────
def copy_table(src_conn, dst_conn, src_table, dst_table, select_sql=None, create_sql=None):
    src_cur = src_conn.cursor()
    dst_cur = dst_conn.cursor()

    if create_sql:
        dst_cur.execute(create_sql)
    else:
        # Derive CREATE TABLE from source schema
        src_cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (src_table,))
        row = src_cur.fetchone()
        if not row:
            print(f"  [SKIP] {src_table} not found in source")
            return 0
        ddl = row[0].replace(f"CREATE TABLE {src_table}",
                              f"CREATE TABLE {dst_table}", 1)
        ddl = ddl.replace(f"CREATE TABLE IF NOT EXISTS {src_table}",
                          f"CREATE TABLE IF NOT EXISTS {dst_table}", 1)
        dst_cur.execute(ddl)

    query = select_sql or f"SELECT * FROM [{src_table}]"
    src_cur.execute(query)
    rows = src_cur.fetchall()

    if rows:
        placeholders = ",".join(["?"] * len(rows[0]))
        dst_cur.executemany(f"INSERT INTO {dst_table} VALUES ({placeholders})", rows)

    dst_conn.commit()
    print(f"  {src_table} -> {dst_table}: {len(rows):,} rows copied")
    return len(rows)


# ──────────────────────────────────────────────────────────────────────────────
# 1. bhav_tb  ← bhavdata_master_tb  (last 60 trading dates)
# ──────────────────────────────────────────────────────────────────────────────
print("Creating bhav_tb ...")
dst.execute("""
CREATE TABLE IF NOT EXISTS bhav_tb (
    bhavid        INTEGER PRIMARY KEY AUTOINCREMENT,
    msid          BIGINT  NOT NULL,
    symbol        TEXT,
    series        TEXT,
    date1         TEXT,
    tsdate        TEXT    NOT NULL,
    prev_close    REAL,
    open_price    REAL,
    high_price    REAL,
    low_price     REAL,
    last_price    REAL,
    close_price   REAL,
    avg_price     REAL,
    ttl_trd_qnty  REAL,
    turnover_lacs REAL,
    no_of_trades  REAL,
    deliv_qty     REAL,
    deliv_per     REAL,
    perc_change   REAL,
    trg           REAL
)
""")
dst.execute("CREATE INDEX IF NOT EXISTS idx_bhav_msid    ON bhav_tb(msid)")
dst.execute("CREATE INDEX IF NOT EXISTS idx_bhav_tsdate  ON bhav_tb(tsdate)")
dst.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_bhav_msid_tsdate ON bhav_tb(msid, tsdate)")

# Get last 60 trading dates from source
src_cur = src.cursor()
src_cur.execute("""
    SELECT DISTINCT tsdate FROM bhavdata_master_tb
    ORDER BY tsdate DESC LIMIT 60
""")
last_60 = [r[0] for r in src_cur.fetchall()]
placeholders = ",".join(["?"] * len(last_60))
src_cur.execute(f"""
    SELECT msid, symbol, series, date1, tsdate,
           prev_close, open_price, high_price, low_price, last_price,
           close_price, avg_price, ttl_trd_qnty, turnover_lacs,
           no_of_trades, deliv_qty, deliv_per, perc_change, trg
    FROM bhavdata_master_tb
    WHERE tsdate IN ({placeholders})
    ORDER BY tsdate, msid
""", last_60)
rows = src_cur.fetchall()
dst.executemany("""
    INSERT INTO bhav_tb (
        msid, symbol, series, date1, tsdate,
        prev_close, open_price, high_price, low_price, last_price,
        close_price, avg_price, ttl_trd_qnty, turnover_lacs,
        no_of_trades, deliv_qty, deliv_per, perc_change, trg
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""", rows)
dst.commit()
print(f"  bhavdata_master_tb -> bhav_tb: {len(rows):,} rows ({len(last_60)} trading dates)")


# ──────────────────────────────────────────────────────────────────────────────
# 2. split_tb  ← splitdata_tb  (all rows)
# ──────────────────────────────────────────────────────────────────────────────
print("\nCreating split_tb ...")
dst.execute("""
CREATE TABLE IF NOT EXISTS split_tb (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol         TEXT,
    msid           BIGINT,
    tsdate         TEXT,
    split_ratio    REAL,
    smooth_ratio   REAL,
    original_ratio REAL,
    prev_close     REAL,
    close          REAL
)
""")
dst.execute("CREATE INDEX IF NOT EXISTS idx_split_tsdate ON split_tb(tsdate)")
src_cur.execute("SELECT symbol, msid, tsdate, split_ratio, smooth_ratio, original_ratio, prev_close, close FROM splitdata_tb ORDER BY tsdate")
rows = src_cur.fetchall()
dst.executemany("INSERT INTO split_tb (symbol,msid,tsdate,split_ratio,smooth_ratio,original_ratio,prev_close,close) VALUES (?,?,?,?,?,?,?,?)", rows)
dst.commit()
print(f"  splitdata_tb -> split_tb: {len(rows):,} rows")


# ──────────────────────────────────────────────────────────────────────────────
# 3. master_tb  ← shareregistry_tb  (all rows, core columns)
# ──────────────────────────────────────────────────────────────────────────────
print("\nCreating master_tb ...")
dst.execute("""
CREATE TABLE IF NOT EXISTS master_tb (
    rid     INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol  TEXT    NOT NULL,
    msid    BIGINT  NOT NULL,
    status  TEXT    NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive', 'deactivate')),
    tsdate  TEXT    NOT NULL,
    UNIQUE(symbol, msid)
)
""")
dst.execute("CREATE INDEX IF NOT EXISTS idx_master_msid ON master_tb(msid)")
src_cur.execute("SELECT symbol, msid, status, tsdate FROM shareregistry_tb ORDER BY msid")
rows = src_cur.fetchall()
dst.executemany("INSERT INTO master_tb (symbol, msid, status, tsdate) VALUES (?,?,?,?)", rows)
dst.commit()
print(f"  shareregistry_tb -> master_tb: {len(rows):,} rows")


# ──────────────────────────────────────────────────────────────────────────────
# 4. rename_tb  ← msidchange_tb  (all rows)
# ──────────────────────────────────────────────────────────────────────────────
print("\nCreating rename_tb ...")
dst.execute("""
CREATE TABLE IF NOT EXISTS rename_tb (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tsdate      TEXT    NOT NULL,
    change_type TEXT,
    old_symbol  TEXT,
    new_symbol  TEXT,
    old_msid    BIGINT,
    new_msid    BIGINT,
    change_date TEXT,
    status      TEXT
)
""")
dst.execute("CREATE INDEX IF NOT EXISTS idx_rename_tsdate ON rename_tb(tsdate)")
src_cur.execute("SELECT tsdate, change_type, old_symbol, new_symbol, old_msid, new_msid, change_date, status FROM msidchange_tb ORDER BY tsdate")
rows = src_cur.fetchall()
dst.executemany("INSERT INTO rename_tb (tsdate,change_type,old_symbol,new_symbol,old_msid,new_msid,change_date,status) VALUES (?,?,?,?,?,?,?,?)", rows)
dst.commit()
print(f"  msidchange_tb -> rename_tb: {len(rows):,} rows")


# ──────────────────────────────────────────────────────────────────────────────
# 5. wmaster_tb  ← master_wdate_tb  (all rows, pipeline-relevant flags only)
# ──────────────────────────────────────────────────────────────────────────────
print("\nCreating wmaster_tb ...")
dst.execute("""
CREATE TABLE IF NOT EXISTS wmaster_tb (
    wid               INTEGER PRIMARY KEY,
    gdate             DATE    NOT NULL,
    tsdate            TEXT    NOT NULL UNIQUE,

    -- Calendar & download
    isholidayflag     INTEGER NOT NULL DEFAULT 0,
    bhavdownload_flag INTEGER NOT NULL DEFAULT 0,

    -- Bhav pipeline stages
    tmpbhvupd_flag    INTEGER NOT NULL DEFAULT 0,
    sharereg_flag     INTEGER NOT NULL DEFAULT 0,
    bhavupdator_flag  INTEGER NOT NULL DEFAULT 0,
    bhavpip_flag      INTEGER NOT NULL DEFAULT 0,

    -- Row counts
    bhavdatarow_count INTEGER DEFAULT 0,
    tmpbhvupd_count   INTEGER DEFAULT 0,

    error_remark      TEXT DEFAULT NULL
)
""")
dst.execute("CREATE INDEX IF NOT EXISTS idx_wmaster_tsdate ON wmaster_tb(tsdate)")

src_cur.execute("""
    SELECT wid, gdate, tsdate,
           isholidayflag, bhavdownload_flag,
           tmpbhvupd_flag, sharereg_flag, bhavupdator_flag, bhavpip_flag,
           bhavdatarow_count, tmpbhvupd_count,
           error_remark
    FROM master_wdate_tb
    ORDER BY wid
""")
rows = src_cur.fetchall()
dst.executemany("""
    INSERT INTO wmaster_tb
    (wid, gdate, tsdate,
     isholidayflag, bhavdownload_flag,
     tmpbhvupd_flag, sharereg_flag, bhavupdator_flag, bhavpip_flag,
     bhavdatarow_count, tmpbhvupd_count, error_remark)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
""", rows)
dst.commit()
print(f"  master_wdate_tb -> wmaster_tb: {len(rows):,} rows (pipeline flags only)")


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== VERIFICATION ===")
dst_cur = dst.cursor()
for tbl in ["bhav_tb", "split_tb", "master_tb", "rename_tb", "wmaster_tb"]:
    dst_cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    count = dst_cur.fetchone()[0]
    print(f"  {tbl}: {count:,} rows")

src.close()
dst.close()
print(f"\nDone -> {DST_DB}")
