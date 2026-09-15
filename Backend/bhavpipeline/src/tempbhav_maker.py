# ====================================================
# File Role    : Support File
# File Name    : tempbhav_maker.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Read NSE bhavcopy CSV → insert into tempbhav_tb
# ====================================================

import os
import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# ─── Resolve paths relative to project root ───
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
RAW_BHAV_PATH  = str(_DATA_DIR / "RawBhvcopy")
SPLIT_JSON_PATH = str(_DATA_DIR / "csvjson")

# ─── Table constants ───
TABLE_TEMPBHAV    = "tempbhav_tb"
TABLE_MASTER_WDATE = "master_wdate_tb"

# ─── Series filter ───
EXCLUDE_SERIES = {"E1", "IV", "P1", "RR", "X1", "GS", "GM", "N3", "GB", "TO"}

# ─── Split detection ───
SPLIT_THRESHOLD_PERCENT = -25.0
STANDARD_SPLIT_RATIOS   = [1.5, 1.75, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50, 100]


def clean_number(value, as_int=False):
    if value is None:
        return 0 if as_int else 0.0
    value_str = str(value).strip()
    if value_str in ('', '-', 'NA', 'NULL', 'N/A'):
        return 0 if as_int else 0.0
    try:
        cleaned = value_str.replace(',', '').strip()
        val = float(cleaned)
        if as_int:
            return int(val) if val == int(val) else int(val)
        return val
    except (ValueError, TypeError):
        return 0 if as_int else 0.0


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


def calculate_split_ratio(prev_close, close):
    if close == 0 or prev_close == 0:
        return 0.0
    raw_ratio = prev_close / close
    rounded_ratio = round(raw_ratio / 0.05) * 0.05
    return round(rounded_ratio, 2)


def get_bhav_csv_path(tsdate):
    tsdate_str = str(tsdate)
    if len(tsdate_str) != 8:
        return None
    year  = tsdate_str[0:4]
    month = tsdate_str[4:6]
    day   = tsdate_str[6:8]
    patterns = [
        f"sec_bhavdata_full_{day}{month}{year}.csv",
        f"sec_bhavdata_full_{day}-{month}-{year}.csv",
        f"cm{day}{month}{year}bhav.csv",
        f"bhav_{tsdate_str}.csv",
    ]
    for pattern in patterns:
        full_path = os.path.join(RAW_BHAV_PATH, pattern)
        if os.path.exists(full_path):
            return full_path
    return None


def read_and_parse_bhav_csv(csv_path, tsdate):
    rows = []
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = '\t' if '\t' in sample else ','
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            def get_val(keys):
                for k in keys:
                    for variant in (k, k.upper(), k.lower()):
                        if variant in row:
                            return row[variant]
                return ''

            symbol = get_val(['SYMBOL', 'symbol']).strip().upper()
            series = get_val(['SERIES', 'series']).strip().upper()

            if not symbol or symbol == 'SYMBOL':
                continue
            if series in EXCLUDE_SERIES:
                continue

            prev_close  = clean_number(get_val(['PREVCLOSE', 'PREV_CLOSE', 'prev_close']))
            open_price  = clean_number(get_val(['OPEN', 'open', 'open_price']))
            high_price  = clean_number(get_val(['HIGH', 'high', 'high_price']))
            low_price   = clean_number(get_val(['LOW', 'low', 'low_price']))
            last_price  = clean_number(get_val(['LAST', 'last', 'last_price']))
            close_price = clean_number(get_val(['CLOSE', 'close', 'close_price']))
            avg_price   = clean_number(get_val(['AVGPRICE', 'AVG_PRICE', 'avg_price']))
            ttl_trd_qnty = clean_number(get_val(['TOTTRDQTY', 'TTL_TRD_QNTY', 'ttl_trd_qnty']), as_int=True)
            turnover     = clean_number(get_val(['TOTTRDVAL', 'TURNOVER', 'turnover_lacs']))
            turnover_lacs = turnover / 100000 if turnover > 100000 else turnover
            no_of_trades = clean_number(get_val(['TOTALTRADES', 'NO_OF_TRADES', 'no_of_trades']), as_int=True)
            deliv_qty    = clean_number(get_val(['DELIV_QTY', 'deliv_qty']), as_int=True)
            deliv_per    = clean_number(get_val(['DELIV_PER', 'deliv_per']))

            perc_change = round(((close_price - prev_close) / prev_close) * 100, 4) if prev_close > 0 else 0.0
            trg = round(high_price - low_price, 4)
            msid = encode_symbol(symbol)
            date1 = get_val(['DATE1', 'TIMESTAMP', 'date1']) or str(tsdate)

            rows.append({
                'msid': msid, 'symbol': symbol, 'series': series if series else 'EQ',
                'date1': date1, 'tsdate': tsdate,
                'prev_close': prev_close, 'open_price': open_price,
                'high_price': high_price, 'low_price': low_price,
                'last_price': last_price, 'close_price': close_price,
                'avg_price': avg_price, 'ttl_trd_qnty': ttl_trd_qnty,
                'turnover_lacs': round(turnover_lacs, 4), 'no_of_trades': no_of_trades,
                'deliv_qty': deliv_qty, 'deliv_per': deliv_per,
                'perc_change': perc_change, 'trg': trg,
            })
    return rows


def detect_splits(rows):
    split_suspects = []
    for row in rows:
        if row['perc_change'] <= SPLIT_THRESHOLD_PERCENT:
            ratio = calculate_split_ratio(row['prev_close'], row['close_price'])
            split_suspects.append({
                'msid': row['msid'], 'symbol': row['symbol'],
                'prev_close': row['prev_close'], 'close': row['close_price'],
                'perc_change': row['perc_change'], 'ratio': ratio,
            })
    return split_suspects


def save_split_info_json(wid, tsdate, split_suspects):
    try:
        os.makedirs(SPLIT_JSON_PATH, exist_ok=True)
        split_shares = []
        for suspect in split_suspects:
            ratio = suspect['ratio']
            if ratio >= 1.0:
                ratio_text = f"1:{int(ratio)} split" if ratio == int(ratio) else f"{ratio}:1 split"
            else:
                ratio_text = f"{1/ratio:.2f}:1 split" if ratio > 0 else "Unknown"
            split_shares.append({
                'msid': suspect['msid'], 'symbol': suspect['symbol'],
                'prev_close': round(suspect['prev_close'], 2),
                'close': round(suspect['close'], 2),
                'ratio': ratio, 'ratio_text': ratio_text,
            })
        split_info = {
            'wid': wid, 'tsdate': str(tsdate),
            'split_count': len(split_shares),
            'detection_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'split_shares': split_shares,
        }
        json_path = os.path.join(SPLIT_JSON_PATH, f"split_info_{tsdate}_wid{wid}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(split_info, f, indent=2, ensure_ascii=False)
        return json_path
    except Exception as e:
        print(f"Error saving split JSON: {e}")
        return None


def update_master_flag(db_path, wid, flag, count, error=""):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE {TABLE_MASTER_WDATE}
            SET tmpbhvupd_flag = ?, tmpbhvupd_count = ?, error_remark = ?
            WHERE wid = ?
        """, (flag, count, error[:500] if error else None, wid))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating master flag: {e}")


def run_tempbhav_maker(tsdate, wid, db_path):
    result = {
        'status': 'failed', 'row_count': 0, 'work_remark': '',
        'errors': [], 'warnings': [],
        'detailed_work': {'split_detected': False, 'split_count': 0, 'split_json_path': None},
    }

    csv_path = get_bhav_csv_path(tsdate)
    if csv_path is None:
        result['errors'].append(f"CSV not found for tsdate={tsdate} in {RAW_BHAV_PATH}")
        result['work_remark'] = "CSV file not found"
        update_master_flag(db_path, wid, flag=-2, count=0, error="CSV file not found")
        return result

    try:
        rows = read_and_parse_bhav_csv(csv_path, tsdate)
    except Exception as e:
        result['errors'].append(f"CSV parse error: {e}")
        result['work_remark'] = "CSV parse failed"
        update_master_flag(db_path, wid, flag=-2, count=0, error=str(e)[:100])
        return result

    if not rows:
        result['errors'].append("No valid data rows in CSV")
        result['work_remark'] = "No data in CSV"
        update_master_flag(db_path, wid, flag=-2, count=0, error="No data in CSV")
        return result

    split_suspects = detect_splits(rows)
    if split_suspects:
        result['detailed_work']['split_detected'] = True
        result['detailed_work']['split_count'] = len(split_suspects)
        result['warnings'].append(f"Split detected: {len(split_suspects)} stocks")

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute(f"DELETE FROM {TABLE_TEMPBHAV} WHERE tsdate = ?", (tsdate,))
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = ?", (TABLE_TEMPBHAV,))

        insert_sql = f"""
            INSERT INTO {TABLE_TEMPBHAV} (
                msid, symbol, series, date1, tsdate, prev_close,
                open_price, high_price, low_price, last_price, close_price,
                avg_price, ttl_trd_qnty, turnover_lacs, no_of_trades,
                deliv_qty, deliv_per, perc_change, trg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for row in rows:
            cursor.execute(insert_sql, (
                row['msid'], row['symbol'], row['series'], row['date1'],
                row['tsdate'], row['prev_close'], row['open_price'],
                row['high_price'], row['low_price'], row['last_price'],
                row['close_price'], row['avg_price'], row['ttl_trd_qnty'],
                row['turnover_lacs'], row['no_of_trades'], row['deliv_qty'],
                row['deliv_per'], row['perc_change'], row['trg'],
            ))
        conn.commit()

        if split_suspects:
            flag_value = -2
            json_path = save_split_info_json(wid, tsdate, split_suspects)
            result['detailed_work']['split_json_path'] = json_path
            error_msg = f"Split ({len(split_suspects)} stocks) - DATA UPLOADED"
        else:
            flag_value = 1
            error_msg = ""

        cursor.execute(f"""
            UPDATE {TABLE_MASTER_WDATE}
            SET tmpbhvupd_flag = ?, tmpbhvupd_count = ?, error_remark = ?
            WHERE wid = ?
        """, (flag_value, len(rows), error_msg or None, wid))
        conn.commit()

        result['status'] = 'success'
        result['row_count'] = len(rows)
        result['work_remark'] = (
            f"Processed {len(rows)} rows, {len(split_suspects)} splits detected (flag=-2)"
            if split_suspects else
            f"Processed {len(rows)} rows successfully (flag=1)"
        )

    except Exception as e:
        if conn:
            conn.rollback()
        result['errors'].append(str(e))
        result['work_remark'] = f"Database error: {e}"
        update_master_flag(db_path, wid, flag=-2, count=0, error=str(e)[:150])

    finally:
        if conn:
            conn.close()

    return result
