# ====================================================
# File Role    : Support File
# File Name    : shareregistry_checker.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Detect new / missing shares and update shareregistry_tb
# ====================================================

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime

_DATA_DIR        = Path(__file__).resolve().parent.parent.parent.parent / "data"
JSON_OUTPUT_PATH = str(_DATA_DIR / "csvjson")

TABLE_SHAREREGISTRY = "shareregistry_tb"
TABLE_TEMPBHAV      = "tempbhav_tb"
TABLE_MASTER_WDATE  = "master_wdate_tb"


def detect_new_shares(conn, tsdate):
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT DISTINCT t.symbol, t.msid FROM {TABLE_TEMPBHAV} t
        WHERE t.tsdate = ?
        AND NOT EXISTS (SELECT 1 FROM {TABLE_SHAREREGISTRY} s WHERE s.msid = t.msid)
    """, (tsdate,))
    return cursor.fetchall()


def detect_missing_shares(conn, tsdate):
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT s.symbol, s.msid FROM {TABLE_SHAREREGISTRY} s
        WHERE s.status = 'active'
        AND NOT EXISTS (
            SELECT 1 FROM {TABLE_TEMPBHAV} t WHERE t.msid = s.msid AND t.tsdate = ?
        )
    """, (tsdate,))
    return cursor.fetchall()


def add_new_shares(conn, tsdate, new_shares):
    cursor = conn.cursor()
    inserted = 0
    for symbol, msid in new_shares:
        try:
            cursor.execute(f"""
                INSERT INTO {TABLE_SHAREREGISTRY} (symbol, msid, status, tsdate)
                VALUES (?, ?, 'active', ?)
            """, (symbol, msid, tsdate))
            inserted += 1
        except sqlite3.IntegrityError:
            continue
    return inserted


def deactivate_missing_shares(conn, missing_shares):
    cursor = conn.cursor()
    updated = 0
    for symbol, msid in missing_shares:
        cursor.execute(f"""
            UPDATE {TABLE_SHAREREGISTRY} SET status = 'deactivate'
            WHERE msid = ? AND status = 'active'
        """, (msid,))
        updated += cursor.rowcount
    return updated


def generate_newold_json(tsdate, new_shares, missing_shares):
    os.makedirs(JSON_OUTPUT_PATH, exist_ok=True)
    report = {
        'tsdate': str(tsdate),
        'generated_at': datetime.now().isoformat(),
        'new_shares': [{'symbol': s, 'msid': m} for s, m in new_shares],
        'missing_shares': [{'symbol': s, 'msid': m} for s, m in missing_shares],
        'summary': {'new_count': len(new_shares), 'missing_count': len(missing_shares)},
    }
    json_path = os.path.join(JSON_OUTPUT_PATH, f"newoldshareinfo_{tsdate}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return json_path


def run_shareregistry_check(tsdate, wid, db_path):
    result = {
        'status': 'failed', 'row_count': 0, 'work_remark': '',
        'errors': [], 'warnings': [],
        'detailed_work': {'new_shares': 0, 'missing_shares': 0, 'json_path': None},
    }

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)

        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_TEMPBHAV} WHERE tsdate = ?", (tsdate,))
        count = cursor.fetchone()[0]
        if count == 0:
            result['errors'].append(f"No tempbhav data for tsdate={tsdate}")
            result['work_remark'] = "No tempbhav data found"
            return result

        new_shares     = detect_new_shares(conn, tsdate)
        missing_shares = detect_missing_shares(conn, tsdate)
        result['detailed_work']['new_shares']     = len(new_shares)
        result['detailed_work']['missing_shares'] = len(missing_shares)

        cursor.execute("BEGIN TRANSACTION")

        if new_shares:
            added = add_new_shares(conn, tsdate, new_shares)
            result['row_count'] = added

        if missing_shares:
            deactivated = deactivate_missing_shares(conn, missing_shares)
            result['warnings'].append(f"Deactivated {deactivated} missing shares")

        flag_value = -2 if missing_shares else 1
        error_msg  = f"Missing {len(missing_shares)} shares" if missing_shares else ""

        cursor.execute(f"""
            UPDATE {TABLE_MASTER_WDATE}
            SET sharereg_flag = ?, shareregrow_count = ?, error_remark = ?
            WHERE wid = ?
        """, (flag_value, len(new_shares), error_msg or None, wid))
        conn.commit()

        json_path = generate_newold_json(tsdate, new_shares, missing_shares)
        result['detailed_work']['json_path'] = json_path
        result['status'] = 'success'
        result['work_remark'] = f"New: {len(new_shares)}, Missing: {len(missing_shares)}"
        if flag_value == -2:
            result['work_remark'] += " (flag=-2, check for renames)"

    except Exception as e:
        if conn:
            conn.rollback()
        result['errors'].append(str(e))
        result['work_remark'] = f"Registry check failed: {e}"

    finally:
        if conn:
            conn.close()

    return result


def find_pending_registry_date(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT wid, tsdate, gdate FROM {TABLE_MASTER_WDATE}
            WHERE sharereg_flag = 0 AND isholidayflag = 1 AND tmpbhvupd_flag IN (1, -2)
            ORDER BY wid ASC LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return row if row else None
    except Exception as e:
        print(f"Error finding pending registry date: {e}")
        return None


def bootstrap_registry(db_path):
    result = {'status': 'failed', 'row_count': 0, 'work_remark': '', 'errors': []}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_SHAREREGISTRY}")
        if cursor.fetchone()[0] > 0:
            result['work_remark'] = "Registry already has data, bootstrap skipped"
            result['status'] = 'success'
            conn.close()
            return result

        cursor.execute(f"SELECT MIN(tsdate) FROM {TABLE_TEMPBHAV}")
        row = cursor.fetchone()
        if not row or not row[0]:
            result['errors'].append("No data in tempbhav_tb for bootstrap")
            conn.close()
            return result

        earliest_date = row[0]
        cursor.execute(f"SELECT DISTINCT symbol, msid FROM {TABLE_TEMPBHAV} WHERE tsdate = ?", (earliest_date,))
        shares = cursor.fetchall()
        inserted = 0
        for symbol, msid in shares:
            try:
                cursor.execute(f"""
                    INSERT INTO {TABLE_SHAREREGISTRY} (symbol, msid, status, tsdate)
                    VALUES (?, ?, 'active', ?)
                """, (symbol, msid, earliest_date))
                inserted += 1
            except sqlite3.IntegrityError:
                continue

        cursor.execute(f"""
            UPDATE {TABLE_MASTER_WDATE} SET sharereg_flag = 1, shareregrow_count = ? WHERE tsdate = ?
        """, (inserted, earliest_date))
        conn.commit()
        conn.close()
        generate_newold_json(earliest_date, shares, [])
        result['status'] = 'success'
        result['row_count'] = inserted
        result['work_remark'] = f"Bootstrap complete: {inserted} shares from {earliest_date}"
    except Exception as e:
        result['errors'].append(str(e))
        result['work_remark'] = f"Bootstrap failed: {e}"
    return result
