# ====================================================
# File Role    : Master File – NSE Bhavcopy Downloader (DB-driven)
# File Name    : nse_bhavcopycsv_downloader_main.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Fetch bhavcopy CSVs from NSE, guided by master_wdate_tb flags
# ====================================================

import os
import sys
import signal
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

# Ensure sibling modules in src/ are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
import nse_bhavcopycsv_logic as logic
from nse_bhavcopycsv_logic import (
    download_bhavcopy_for_trade_date,
    download_with_phased_retry,
    wait_with_countdown,
    is_termination_requested,
)

_DATA_DIR    = Path(__file__).resolve().parent.parent.parent.parent / "data"
DB_DIR       = str(_DATA_DIR / "db")
RAW_BHAV_DIR = str(_DATA_DIR / "RawBhvcopy")

DB_NAME                = "Nse_Mainbhavdata.db"
OUTPUT_BHAV_CSV_PREFIX = "sec_bhavdata_full_"
DB_FILE                = os.path.join(DB_DIR, DB_NAME)
MASTER_WDATE_TABLE     = "master_wdate_tb"
MAX_BHAV_DOWNLOADS_PER_RUN = 10


def signal_handler(signum, frame):
    logic._termination_requested = True
    print("\n[STOP] Ctrl+C detected — graceful shutdown initiated.")


def setup_signal_handlers():
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal_handler)


def ensure_directories():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(RAW_BHAV_DIR, exist_ok=True)


def connect_db():
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database not found: {DB_FILE}")
    return sqlite3.connect(DB_FILE)


def get_current_date_yyyymmdd():
    return datetime.now().strftime("%Y%m%d")


def parse_tsdate(tsdate: str) -> Tuple[str, str]:
    tsdate = tsdate.strip()
    for fmt in ["%Y%m%d", "%d%m%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            dt = datetime.strptime(tsdate, fmt)
            return dt.strftime("%d-%m-%Y"), dt.strftime("%d%m%Y")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse tsdate='{tsdate}'")


def normalize_tsdate_to_yyyymmdd(tsdate: str) -> str:
    for fmt in ["%Y%m%d", "%d%m%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(tsdate.strip(), fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    raise ValueError(f"Cannot normalize tsdate='{tsdate}'")


def check_bhavfile_exists(ddmmyyyy_str: str) -> Tuple[bool, int, str]:
    filename = f"{OUTPUT_BHAV_CSV_PREFIX}{ddmmyyyy_str}.csv"
    filepath = os.path.join(RAW_BHAV_DIR, filename)
    if not os.path.exists(filepath):
        return False, 0, filepath
    try:
        import pandas as pd
        df = pd.read_csv(filepath)
        row_count = len(df)
        if row_count == 0:
            return False, 0, filepath
        return True, row_count, filepath
    except Exception as e:
        print(f"[WARN] Cannot read file: {filepath} | {e}")
        return False, 0, filepath


def fetch_next_pending_row(conn):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(f"""
        SELECT wid, gdate, tsdate, isholidayflag, bhavdownload_flag,
               bhavupdator_flag, ematable_flag, bhavdatarow_count
        FROM {MASTER_WDATE_TABLE}
        WHERE bhavdownload_flag = 0
        ORDER BY wid ASC LIMIT 1
    """)
    return cur.fetchone()


def mark_non_trading_day_handled(conn, wid):
    conn.execute(f"UPDATE {MASTER_WDATE_TABLE} SET bhavdownload_flag = -1, bhavdatarow_count = COALESCE(bhavdatarow_count, 0) WHERE wid = ?", (wid,))
    conn.commit()


def mark_as_holiday_and_reset_flags(conn, wid):
    conn.execute(f"""
        UPDATE {MASTER_WDATE_TABLE}
        SET isholidayflag = 0, bhavdownload_flag = -1, bhavupdator_flag = -1,
            ematable_flag = -1, bhavdatarow_count = 0
        WHERE wid = ?
    """, (wid,))
    conn.commit()
    print(f"[DB] wid={wid} marked as holiday.")


def mark_existing_file_handled(conn, wid, row_count):
    conn.execute(f"UPDATE {MASTER_WDATE_TABLE} SET bhavdownload_flag = 1, bhavdatarow_count = ? WHERE wid = ?", (row_count, wid))
    conn.commit()


def update_download_success(conn, wid, row_count):
    conn.execute(f"UPDATE {MASTER_WDATE_TABLE} SET bhavdownload_flag = 1, bhavdatarow_count = ? WHERE wid = ?", (row_count, wid))
    conn.commit()


def handle_past_date_failure(conn, wid, tsdate) -> bool:
    print(f"\n{'='*60}")
    print(f"PAST DATE DOWNLOAD FAILED — wid={wid}, tsdate={tsdate}")
    print("Options: [Y] Mark as holiday  [N] Terminate")
    while True:
        if is_termination_requested():
            return False
        try:
            choice = input("Mark as holiday? (Y/N): ").strip().upper()
        except EOFError:
            return False
        if choice == "Y":
            mark_as_holiday_and_reset_flags(conn, wid)
            return True
        elif choice == "N":
            return False
        else:
            print("Enter Y or N.")


def process_single_row(conn, row) -> Tuple[bool, bool, bool, bool]:
    wid     = row["wid"]
    tsdate  = row["tsdate"]
    is_flag = row["isholidayflag"]
    print(f"\n--- Processing wid={wid}, tsdate='{tsdate}', isholidayflag={is_flag}")

    if is_flag == 0:
        mark_non_trading_day_handled(conn, wid)
        return True, False, False, False

    try:
        trade_date_str, ddmmyyyy_str = parse_tsdate(tsdate)
        tsdate_normalized = normalize_tsdate_to_yyyymmdd(tsdate)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return False, False, False, False

    file_exists, existing_row_count, filepath = check_bhavfile_exists(ddmmyyyy_str)
    if file_exists:
        print(f"[SKIP] File already exists ({existing_row_count} rows): {filepath}")
        mark_existing_file_handled(conn, wid, existing_row_count)
        return True, False, True, False

    current_date = get_current_date_yyyymmdd()

    if tsdate_normalized == current_date:
        success, row_count = download_with_phased_retry(trade_date_str, ddmmyyyy_str, wid)
        if success:
            update_download_success(conn, wid, row_count)
            return True, True, False, False
        return False, False, False, True

    elif tsdate_normalized < current_date:
        try:
            row_count = download_bhavcopy_for_trade_date(trade_date_str, ddmmyyyy_str)
            update_download_success(conn, wid, row_count)
            return True, True, False, False
        except Exception as e:
            print(f"[FAIL] {e}")
        user_continue = handle_past_date_failure(conn, wid, tsdate)
        return (True, False, False, False) if user_continue else (False, False, False, True)

    else:
        print(f"[WARN] Future date {tsdate_normalized} — skipping.")
        return False, False, False, False


def run_bhavcopy_downloader_batch():
    ensure_directories()
    try:
        conn = connect_db()
    except FileNotFoundError as e:
        print(f"[FATAL] {e}")
        return

    downloads_done = files_skipped = holidays_marked = 0
    should_terminate = False

    while True:
        if is_termination_requested():
            break
        row = fetch_next_pending_row(conn)
        if row is None:
            print("[INFO] No pending rows with bhavdownload_flag=0.")
            break
        if downloads_done >= MAX_BHAV_DOWNLOADS_PER_RUN:
            print(f"[STOP] Reached MAX_BHAV_DOWNLOADS_PER_RUN={MAX_BHAV_DOWNLOADS_PER_RUN}.")
            break

        processed, downloaded, skipped_existing, should_terminate = process_single_row(conn, row)
        if downloaded:
            downloads_done += 1
        if skipped_existing:
            files_skipped += 1
        if processed and not downloaded and not skipped_existing:
            holidays_marked += 1
        if should_terminate:
            break
        if not processed and not should_terminate:
            continue

    conn.close()
    print(f"\n=== BATCH SUMMARY: downloads={downloads_done}, skipped={files_skipped}, holidays={holidays_marked} ===")


if __name__ == "__main__":
    setup_signal_handlers()
    run_bhavcopy_downloader_batch()
