# ====================================================
# File Role    : Master File
# File Name    : pipeline_runner.py
# Location     : backend/
# Purpose      : Orchestrate all 5 pipeline stages for pending trading dates
# ====================================================

import sys
import logging
import sqlite3
from pathlib import Path

# Make bhavpipeline/src importable
_SRC_DIR = Path(__file__).resolve().parent / "bhavpipeline" / "src"
sys.path.insert(0, str(_SRC_DIR))

from paths import DB_PATH

from tempbhav_maker       import run_tempbhav_maker
from split_corrector      import run_split_correction
from shareregistry_checker import run_shareregistry_check
from msid_rename_handler  import run_msid_rename
from tempbhav_to_master   import run_tempbhav_to_master

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline_runner")

TABLE_WDATE = "master_wdate_tb"


def get_eligible_date(db_path: str):
    """Return (wid, tsdate) for the oldest pending eligible trading date, or (None, None)."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT wid, tsdate FROM {TABLE_WDATE}
            WHERE tmpbhvupd_flag = 0
              AND isholidayflag  = 1
              AND bhavdownload_flag = 1
            ORDER BY wid ASC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return (row[0], row[1]) if row else (None, None)
    except Exception as e:
        log.error(f"Error finding eligible date: {e}")
        return None, None


def run_pipeline_for_date(wid: int, tsdate: str, db_path: str) -> bool:
    """
    Execute all pipeline stages for a single trading date.
    Returns True on full success, False on any stage failure.
    """
    log.info(f"{'='*55}")
    log.info(f"Pipeline start  wid={wid}  tsdate={tsdate}")
    log.info(f"{'='*55}")

    # ── Stage 1: Load raw CSV into tempbhav_tb ──────────────────
    log.info("[1/5] TempBhav Maker")
    r1 = run_tempbhav_maker(tsdate, wid, db_path)
    log.info(f"      {r1['work_remark']}")
    if r1['status'] != 'success':
        log.error(f"      FAILED: {r1['errors']}")
        return False

    # ── Stage 2: Correct splits (only if detected) ──────────────
    if r1['detailed_work'].get('split_detected'):
        log.info(f"[2/5] Split Corrector  ({r1['detailed_work']['split_count']} splits)")
        r2 = run_split_correction(tsdate, wid, db_path)
        log.info(f"      {r2['work_remark']}")
        if r2['warnings']:
            for w in r2['warnings']:
                log.warning(f"      {w}")
    else:
        log.info("[2/5] Split Corrector  — skipped (no splits)")

    # ── Stage 3: Share Registry ─────────────────────────────────
    log.info("[3/5] Share Registry Checker")
    r3 = run_shareregistry_check(tsdate, wid, db_path)
    log.info(f"      {r3['work_remark']}")
    if r3['status'] != 'success':
        log.error(f"      FAILED: {r3['errors']}")
        return False

    # ── Stage 4: MSID Rename (only if missing shares) ───────────
    if r3['detailed_work'].get('missing_shares', 0) > 0:
        log.info(f"[4/5] MSID Rename Handler  ({r3['detailed_work']['missing_shares']} missing)")
        r4 = run_msid_rename(tsdate, wid, db_path)
        log.info(f"      {r4['work_remark']}")
        if r4['warnings']:
            for w in r4['warnings']:
                log.warning(f"      {w}")
    else:
        log.info("[4/5] MSID Rename Handler — skipped (no missing shares)")

    # ── Stage 5: Transfer staging → master ──────────────────────
    log.info("[5/5] TempBhav → Master Transfer")
    r5 = run_tempbhav_to_master(tsdate, wid, db_path)
    log.info(f"      {r5['work_remark']}")
    if r5['status'] != 'success':
        log.error(f"      FAILED: {r5['errors']}")
        return False

    log.info(f"Pipeline complete  wid={wid}  tsdate={tsdate}")
    return True


def run_pipeline_batch(db_path: str = DB_PATH, max_days: int = 10) -> dict:
    """
    Process up to max_days pending trading dates in sequence.
    Called automatically on backend startup and via API endpoint.
    """
    log.info(f"Batch started (max_days={max_days})")
    processed = failed = 0

    for _ in range(max_days):
        wid, tsdate = get_eligible_date(db_path)
        if wid is None:
            log.info("No more eligible dates — batch complete.")
            break

        success = run_pipeline_for_date(wid, tsdate, db_path)
        if success:
            processed += 1
        else:
            failed += 1
            log.warning(f"Stopping batch after failure on wid={wid}.")
            break

    summary = {"processed": processed, "failed": failed}
    log.info(f"Batch finished: {summary}")
    return summary
