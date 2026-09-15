# ====================================================
# File Role    : Support File
# File Name    : nse_bhavcopycsv_logic.py
# Location     : backend/bhavpipeline/src/
# Purpose      : NSE bhavcopy API download + phased retry logic
# ====================================================

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Tuple

import pandas as pd
from nselib import capital_market

_DATA_DIR    = Path(__file__).resolve().parent.parent.parent.parent / "data"
RAW_BHAV_DIR = str(_DATA_DIR / "RawBhvcopy")

PHASE1_ATTEMPTS     = 5
PHASE1_INTERVAL_SEC = 5 * 60

PHASE2_ATTEMPTS     = 5
PHASE2_INTERVAL_SEC = 30 * 60

OUTPUT_BHAV_CSV_PREFIX = "sec_bhavdata_full_"

_termination_requested = False


def is_termination_requested() -> bool:
    return _termination_requested


def download_bhavcopy_for_trade_date(trade_date_str: str, ddmmyyyy_str: str) -> int:
    datetime.strptime(trade_date_str, "%d-%m-%Y")
    df = capital_market.bhav_copy_with_delivery(trade_date=trade_date_str)
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise RuntimeError(f"Downloaded bhavcopy is empty for {trade_date_str}")
    filename  = f"{OUTPUT_BHAV_CSV_PREFIX}{ddmmyyyy_str}.csv"
    full_path = os.path.join(RAW_BHAV_DIR, filename)
    df.to_csv(full_path, index=False)
    print(f"[OK] Bhavcopy saved → {full_path} (rows: {len(df)})")
    return len(df)


def wait_with_countdown(seconds: int, message_prefix: str = "Next attempt in") -> bool:
    print(f"\n{message_prefix} {seconds // 60} min {seconds % 60} sec...")
    for remaining in range(seconds, 0, -1):
        if is_termination_requested():
            return False
        mins, secs = divmod(remaining, 60)
        print(f"\r⏳ Waiting: {mins:02d}:{secs:02d} remaining...", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 40 + "\r", end="")
    return True


def download_with_phased_retry(trade_date_str: str, ddmmyyyy_str: str, wid: int) -> Tuple[bool, int]:
    print(f"\n[PHASE1] Starting Phase 1 retry ({PHASE1_ATTEMPTS}x @ {PHASE1_INTERVAL_SEC//60}min)")
    for attempt in range(1, PHASE1_ATTEMPTS + 1):
        if is_termination_requested():
            return False, 0
        print(f"\n[P1-{attempt}/{PHASE1_ATTEMPTS}] Attempt for wid={wid}, date={trade_date_str}")
        try:
            row_count = download_bhavcopy_for_trade_date(trade_date_str, ddmmyyyy_str)
            return True, row_count
        except Exception as e:
            print(f"[FAIL] Attempt {attempt} failed: {e}")
        if attempt < PHASE1_ATTEMPTS:
            if not wait_with_countdown(PHASE1_INTERVAL_SEC, "Phase 1 retry in"):
                return False, 0

    print(f"\n[PHASE2] Starting Phase 2 retry ({PHASE2_ATTEMPTS}x @ {PHASE2_INTERVAL_SEC//60}min)")
    for attempt in range(1, PHASE2_ATTEMPTS + 1):
        if is_termination_requested():
            return False, 0
        print(f"\n[P2-{attempt}/{PHASE2_ATTEMPTS}] Attempt for wid={wid}, date={trade_date_str}")
        try:
            row_count = download_bhavcopy_for_trade_date(trade_date_str, ddmmyyyy_str)
            return True, row_count
        except Exception as e:
            print(f"[FAIL] Attempt {attempt} failed: {e}")
        if attempt < PHASE2_ATTEMPTS:
            if not wait_with_countdown(PHASE2_INTERVAL_SEC, "Phase 2 retry in"):
                return False, 0

    print("[EXHAUSTED] All retry attempts failed.")
    return False, 0
