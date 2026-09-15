# ====================================================
# File Role    : Support File
# File Name    : msid_rename_handler.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Process NSE symbol renames and update historical data
# ====================================================

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime

_DATA_DIR         = Path(__file__).resolve().parent.parent.parent.parent / "data"
JSON_INPUT_FOLDER = str(_DATA_DIR / "csvjson")
JSON_LOGS_FOLDER  = str(_DATA_DIR / "csvjson")

TABLE_BHAVDATA_MASTER = "bhavdata_master_tb"
TABLE_SHAREREGISTRY   = "shareregistry_tb"
TABLE_MSIDCHANGE      = "msidchange_tb"
TABLE_MASTER_WDATE    = "master_wdate_tb"


def encode_symbol(symbol):
    symbol = str(symbol).upper().strip()
    if not symbol:
        return "9000000000000"
    hash_value = 0
    primes = [31, 37, 41, 43, 47, 53, 59, 61, 67, 71]
    for i, char in enumerate(symbol[:20]):
        if char.isalpha():
            val = ord(char) - ord('A') + 1
        elif char.isdigit():
            val = ord(char) - ord('0') + 27
        else:
            val = 37
        prime = primes[i % len(primes)]
        hash_value = (hash_value * prime + val * (i + 1)) % 1000000000000
    hash_value = (hash_value + len(symbol) * 999999999) % 1000000000000
    return '9' + str(hash_value).zfill(12)


def load_symbolchange_mapping(json_path):
    if not os.path.exists(json_path):
        return {}
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
        mapping = {}
        for record in records:
            old_symbol = record.get('SM_KEY_SYMBOL', '').upper().strip()
            new_symbol = record.get('SM_NEW_SYMBOL', '').upper().strip()
            change_date = record.get('SM_APPLICABLE_FROM', '')
            if old_symbol and new_symbol:
                mapping[old_symbol] = {'new_symbol': new_symbol, 'date': change_date}
        return mapping
    except Exception as e:
        print(f"Error loading symbolchange.json: {e}")
        return {}


def load_newoldshareinfo(tsdate):
    json_path = os.path.join(JSON_INPUT_FOLDER, f"newoldshareinfo_{tsdate}.json")
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading newoldshareinfo: {e}")
        return None


def classify_missing_shares(missing_shares, symbolchange_mapping):
    renamed, delisted = [], []
    for share in missing_shares:
        symbol = share.get('symbol', '').upper().strip()
        msid   = share.get('msid', '')
        if symbol in symbolchange_mapping:
            change_info = symbolchange_mapping[symbol]
            new_symbol = change_info['new_symbol']
            new_msid   = encode_symbol(new_symbol)
            renamed.append({
                'old_share': {'symbol': symbol, 'msid': msid},
                'new_share': {'symbol': new_symbol, 'msid': new_msid},
                'change_info': change_info,
            })
        else:
            delisted.append({'symbol': symbol, 'msid': msid})
    return {'renamed': renamed, 'delisted': delisted, 'genuinely_new': []}


def get_historical_tsdates(conn, wid):
    cursor = conn.cursor()
    cursor.execute(f"SELECT tsdate FROM {TABLE_MASTER_WDATE} WHERE wid >= 1 AND wid <= ? ORDER BY wid ASC", (wid,))
    return [row[0] for row in cursor.fetchall()]


def update_all_historical_data(conn, wid, old_symbol, old_msid, new_symbol, new_msid):
    cursor = conn.cursor()
    historical_tsdates = get_historical_tsdates(conn, wid)
    if not historical_tsdates:
        return {'total_rows_updated': 0, 'tsdates_with_updates': []}
    placeholders = ','.join(['?' for _ in historical_tsdates])
    cursor.execute(f"""
        UPDATE {TABLE_BHAVDATA_MASTER}
        SET symbol = ?, msid = CAST(? AS INTEGER)
        WHERE CAST(msid AS INTEGER) = CAST(? AS INTEGER)
        AND tsdate IN ({placeholders})
    """, (new_symbol, new_msid, old_msid, *historical_tsdates))
    rows_updated = cursor.rowcount
    affected = []
    if rows_updated > 0:
        cursor.execute(f"""
            SELECT DISTINCT tsdate FROM {TABLE_BHAVDATA_MASTER}
            WHERE symbol = ? AND tsdate IN ({placeholders})
        """, (new_symbol, *historical_tsdates))
        affected = [r[0] for r in cursor.fetchall()]
    return {'total_rows_updated': rows_updated, 'tsdates_with_updates': affected}


def update_shareregistry(conn, wid, old_symbol, new_symbol, new_msid, tsdate):
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE {TABLE_SHAREREGISTRY} SET status = 'deactivate'
        WHERE symbol = ? AND status = 'active'
    """, (old_symbol,))
    try:
        cursor.execute(f"""
            INSERT INTO {TABLE_SHAREREGISTRY} (symbol, msid, status, tsdate) VALUES (?, ?, 'active', ?)
        """, (new_symbol, new_msid, tsdate))
    except sqlite3.IntegrityError:
        cursor.execute(f"UPDATE {TABLE_SHAREREGISTRY} SET status = 'active' WHERE msid = ?", (new_msid,))
    return True


def insert_into_msidchange_tb(conn, tsdate, old_symbol, old_msid, new_symbol, new_msid, change_type):
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({TABLE_MSIDCHANGE})")
        columns = [col[1] for col in cursor.fetchall()]
        if not columns:
            return False
        if 'old_msid' in columns and 'new_msid' in columns:
            cursor.execute(f"""
                INSERT INTO {TABLE_MSIDCHANGE}
                (tsdate, old_symbol, old_msid, new_symbol, new_msid, change_type, change_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (tsdate, old_symbol, old_msid, new_symbol, new_msid, change_type, datetime.now().isoformat()))
        else:
            cursor.execute(f"""
                INSERT INTO {TABLE_MSIDCHANGE} (tsdate, old_symbol, new_symbol, change_type)
                VALUES (?, ?, ?, ?)
            """, (tsdate, old_symbol, new_symbol, change_type))
        return True
    except Exception as e:
        print(f"Error logging to msidchange_tb: {e}")
        return False


def save_rename_log(tsdate, classification, results):
    os.makedirs(JSON_LOGS_FOLDER, exist_ok=True)
    log = {
        'tsdate': str(tsdate),
        'processed_at': datetime.now().isoformat(),
        'classification_summary': {
            'total_renamed': len(classification.get('renamed', [])),
            'total_delisted': len(classification.get('delisted', [])),
        },
        'renamed_details': classification.get('renamed', []),
        'delisted_shares': classification.get('delisted', []),
        'processing_results': results,
    }
    log_path = os.path.join(JSON_LOGS_FOLDER, f"rename_log_{tsdate}.json")
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    return log_path


def _set_sharereg_flag_1(db_path, wid):
    conn = sqlite3.connect(db_path)
    conn.execute(f"UPDATE {TABLE_MASTER_WDATE} SET sharereg_flag = 1 WHERE wid = ?", (wid,))
    conn.commit()
    conn.close()


def run_msid_rename(tsdate, wid, db_path):
    result = {
        'status': 'failed', 'row_count': 0, 'work_remark': '',
        'errors': [], 'warnings': [],
        'detailed_work': {
            'renames_processed': 0, 'delisted_count': 0,
            'bhavdata_rows_updated': 0, 'log_path': None,
        },
    }

    newold_info = load_newoldshareinfo(tsdate)
    if newold_info is None or not newold_info.get('missing_shares'):
        try:
            _set_sharereg_flag_1(db_path, wid)
            result['status'] = 'success'
            result['work_remark'] = "No missing shares to process"
        except Exception as e:
            result['errors'].append(str(e))
        return result

    missing_shares = newold_info.get('missing_shares', [])
    symbolchange_path = os.path.join(JSON_INPUT_FOLDER, "symbolchange.json")
    symbolchange_mapping = load_symbolchange_mapping(symbolchange_path)
    if not symbolchange_mapping:
        result['warnings'].append("symbolchange.json not found or empty")

    classification = classify_missing_shares(missing_shares, symbolchange_mapping)
    result['detailed_work']['delisted_count'] = len(classification['delisted'])

    conn = None
    processing_results = []
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")

        for rename in classification['renamed']:
            old_share  = rename['old_share']
            new_share  = rename['new_share']
            old_symbol = old_share['symbol']
            old_msid   = old_share['msid']
            new_symbol = new_share['symbol']
            new_msid   = new_share['msid']
            try:
                stats = update_all_historical_data(conn, wid, old_symbol, old_msid, new_symbol, new_msid)
                result['detailed_work']['bhavdata_rows_updated'] += stats['total_rows_updated']
                update_shareregistry(conn, wid, old_symbol, new_symbol, new_msid, tsdate)
                insert_into_msidchange_tb(conn, tsdate, old_symbol, old_msid, new_symbol, new_msid, 'rename')
                result['detailed_work']['renames_processed'] += 1
                processing_results.append({
                    'old_symbol': old_symbol, 'new_symbol': new_symbol,
                    'status': 'success', 'rows_updated': stats['total_rows_updated'],
                })
            except Exception as e:
                processing_results.append({'old_symbol': old_symbol, 'new_symbol': new_symbol, 'status': 'failed', 'error': str(e)})
                result['warnings'].append(f"Failed to process {old_symbol}: {e}")

        for delisted in classification['delisted']:
            insert_into_msidchange_tb(conn, tsdate, delisted['symbol'], delisted['msid'], '', '', 'delisted')

        cursor.execute(f"UPDATE {TABLE_MASTER_WDATE} SET sharereg_flag = 1 WHERE wid = ?", (wid,))
        conn.commit()

        log_path = save_rename_log(tsdate, classification, processing_results)
        result['detailed_work']['log_path'] = log_path
        result['status'] = 'success'
        result['row_count'] = result['detailed_work']['bhavdata_rows_updated']
        result['work_remark'] = (
            f"Renames: {result['detailed_work']['renames_processed']}, "
            f"Delisted: {result['detailed_work']['delisted_count']}"
        )

    except Exception as e:
        if conn:
            conn.rollback()
        result['errors'].append(str(e))
        result['work_remark'] = f"Rename processing failed: {e}"

    finally:
        if conn:
            conn.close()

    return result


def get_pending_rename_wids(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT wid, tsdate FROM {TABLE_MASTER_WDATE} WHERE sharereg_flag = -2 ORDER BY wid ASC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting pending rename WIDs: {e}")
        return []
