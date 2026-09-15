# ====================================================
# File Role    : Support File
# File Name    : split_corrector.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Detect and correct stock splits in tempbhav + master tables
# ====================================================

import os
import json
import csv
import sqlite3
from pathlib import Path
from datetime import datetime

# ─── Resolve paths relative to project root ───
_DATA_DIR       = Path(__file__).resolve().parent.parent.parent.parent / "data"
JSON_PATH       = str(_DATA_DIR / "csvjson")
CSV_EXPORT_PATH = str(_DATA_DIR / "csvjson")

TABLE_TEMPBHAV       = "tempbhav_tb"
TABLE_BHAVDATA_MASTER = "bhavdata_master_tb"
TABLE_MASTER_WDATE   = "master_wdate_tb"

STANDARD_SPLIT_RATIOS = [1.5, 1.75, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50, 100]
MAX_DEVIATION_PERCENT = 15.0
PRICE_COLUMNS = ['open_price', 'high_price', 'low_price', 'last_price',
                 'close_price', 'prev_close', 'avg_price', 'trg']


def smooth_split_ratio(calculated_ratio):
    if calculated_ratio <= 0:
        return {
            'smoothed_ratio': 0.0, 'original_ratio': calculated_ratio,
            'deviation_percent': 0.0, 'is_within_tolerance': False,
            'alert_message': 'Invalid ratio (zero or negative)', 'ratio_text': 'Invalid ratio',
        }
    nearest_ratio = min(STANDARD_SPLIT_RATIOS, key=lambda x: abs(x - calculated_ratio))
    deviation_percent = abs((nearest_ratio - calculated_ratio) / calculated_ratio) * 100
    is_within_tolerance = deviation_percent <= MAX_DEVIATION_PERCENT

    if nearest_ratio >= 1.0:
        ratio_text = f"1:{int(nearest_ratio)} split" if nearest_ratio == int(nearest_ratio) else f"{nearest_ratio}:1 split"
    else:
        ratio_text = f"{1/nearest_ratio:.2f}:1 split" if nearest_ratio > 0 else "Unknown"

    alert_message = (
        f"Ratio {calculated_ratio:.2f} deviates {deviation_percent:.2f}% from nearest {nearest_ratio}"
        if not is_within_tolerance else ""
    )
    return {
        'smoothed_ratio': nearest_ratio,
        'original_ratio': round(calculated_ratio, 2),
        'deviation_percent': round(deviation_percent, 2),
        'is_within_tolerance': is_within_tolerance,
        'alert_message': alert_message,
        'ratio_text': ratio_text,
    }


def find_split_json_file(tsdate, wid):
    json_path = os.path.join(JSON_PATH, f"split_info_{tsdate}_wid{wid}.json")
    return json_path if os.path.exists(json_path) else None


def get_historical_tsdates_by_wid(conn, split_tsdate):
    cursor = conn.cursor()
    cursor.execute(f"SELECT wid FROM {TABLE_MASTER_WDATE} WHERE tsdate = ?", (str(split_tsdate),))
    row = cursor.fetchone()
    if not row:
        return []
    split_wid = row[0]
    cursor.execute(f"SELECT tsdate FROM {TABLE_MASTER_WDATE} WHERE wid >= 1 AND wid < ? ORDER BY wid ASC", (split_wid,))
    return [r[0] for r in cursor.fetchall()]


def apply_split_correction_tempbhav(conn, msid, split_tsdate, ratio):
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE {TABLE_TEMPBHAV}
        SET prev_close = prev_close / ?
        WHERE CAST(msid AS INTEGER) = CAST(? AS INTEGER) AND tsdate = ?
    """, (ratio, msid, split_tsdate))
    return cursor.rowcount


def apply_split_correction_bhav_master(conn, msid, historical_tsdates, ratio):
    if not historical_tsdates:
        return 0
    cursor = conn.cursor()
    placeholders = ','.join(['?' for _ in historical_tsdates])
    cursor.execute(f"""
        UPDATE {TABLE_BHAVDATA_MASTER}
        SET open_price  = open_price / ?,
            high_price  = high_price / ?,
            low_price   = low_price / ?,
            last_price  = last_price / ?,
            close_price = close_price / ?,
            prev_close  = prev_close / ?,
            avg_price   = avg_price / ?,
            trg         = trg / ?,
            ttl_trd_qnty = CAST(ttl_trd_qnty * ? AS INTEGER)
        WHERE CAST(msid AS INTEGER) = CAST(? AS INTEGER)
        AND tsdate IN ({placeholders})
    """, (ratio, ratio, ratio, ratio, ratio, ratio, ratio, ratio, ratio, msid, *historical_tsdates))
    return cursor.rowcount


def write_correction_report_csv(correction_report, tsdate, wid):
    os.makedirs(CSV_EXPORT_PATH, exist_ok=True)
    csv_path = os.path.join(CSV_EXPORT_PATH, f"split_correction_report_{tsdate}_wid{wid}.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['symbol', 'msid', 'original_ratio', 'smoothed_ratio',
                         'deviation_percent', 'within_tolerance', 'tempbhav_updated', 'master_updated'])
        for item in correction_report:
            writer.writerow([
                item.get('symbol', ''), item.get('msid', ''),
                item.get('original_ratio', ''), item.get('smoothed_ratio', ''),
                item.get('deviation_percent', ''), item.get('within_tolerance', ''),
                item.get('tempbhav_updated', 0), item.get('master_updated', 0),
            ])
    return csv_path


def run_split_correction(tsdate, wid, db_path):
    result = {
        'status': 'failed', 'row_count': 0, 'work_remark': '',
        'errors': [], 'warnings': [],
        'detailed_work': {'splits_corrected': 0, 'tempbhav_rows': 0,
                          'bhavmaster_rows': 0, 'csv_report_path': None},
    }

    json_file = find_split_json_file(tsdate, wid)
    if json_file is None:
        result['errors'].append(f"Split JSON not found for tsdate={tsdate}, wid={wid}")
        result['work_remark'] = "Split JSON file not found"
        return result

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            split_info = json.load(f)
    except Exception as e:
        result['errors'].append(f"Invalid JSON: {e}")
        result['work_remark'] = "Invalid JSON file"
        return result

    if split_info.get('split_count', 0) == 0:
        result['status'] = 'success'
        result['work_remark'] = "No splits to correct"
        return result

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        historical_tsdates = get_historical_tsdates_by_wid(conn, tsdate)
        correction_report = []
        cursor.execute("BEGIN TRANSACTION")

        for split_share in split_info.get('split_shares', []):
            msid     = split_share.get('msid', '')
            symbol   = split_share.get('symbol', '')
            orig_ratio = split_share.get('ratio', 0)
            smoothed = smooth_split_ratio(orig_ratio)
            ratio_to_use = smoothed['smoothed_ratio']

            if not smoothed['is_within_tolerance']:
                result['warnings'].append(f"High deviation for {symbol}: {smoothed['deviation_percent']}%")
            if ratio_to_use <= 0:
                result['warnings'].append(f"Invalid ratio for {symbol}, skipping")
                continue

            tempbhav_updated = apply_split_correction_tempbhav(conn, msid, tsdate, ratio_to_use)
            master_updated   = apply_split_correction_bhav_master(conn, msid, historical_tsdates, ratio_to_use)
            result['detailed_work']['tempbhav_rows'] += tempbhav_updated
            result['detailed_work']['bhavmaster_rows'] += master_updated
            result['detailed_work']['splits_corrected'] += 1
            correction_report.append({
                'symbol': symbol, 'msid': msid,
                'original_ratio': smoothed['original_ratio'],
                'smoothed_ratio': smoothed['smoothed_ratio'],
                'deviation_percent': smoothed['deviation_percent'],
                'within_tolerance': smoothed['is_within_tolerance'],
                'tempbhav_updated': tempbhav_updated,
                'master_updated': master_updated,
            })

        cursor.execute(f"""
            UPDATE {TABLE_MASTER_WDATE}
            SET tmpbhvupd_flag = 1, error_remark = 'Split corrected'
            WHERE wid = ?
        """, (wid,))
        conn.commit()

        csv_path = write_correction_report_csv(correction_report, tsdate, wid)
        result['detailed_work']['csv_report_path'] = csv_path
        result['status'] = 'success'
        result['row_count'] = result['detailed_work']['bhavmaster_rows']
        result['work_remark'] = (
            f"Corrected {result['detailed_work']['splits_corrected']} splits, "
            f"updated {result['detailed_work']['bhavmaster_rows']} master rows"
        )

    except Exception as e:
        if conn:
            conn.rollback()
        result['errors'].append(str(e))
        result['work_remark'] = f"Split correction failed: {e}"

    finally:
        if conn:
            conn.close()

    return result


def get_split_error_wids(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT wid, tsdate FROM {TABLE_MASTER_WDATE} WHERE tmpbhvupd_flag = -2 ORDER BY wid ASC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting split error WIDs: {e}")
        return []
