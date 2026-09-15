# ====================================================
# File Role    : Support File
# File Name    : symbolchange_downloader.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Download NSE symbol change CSV and convert to JSON
# ====================================================

import os
import csv
import json
import time
import re
from pathlib import Path
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

_DATA_DIR  = Path(__file__).resolve().parent.parent.parent.parent / "data"
OUTPUT_DIR = str(_DATA_DIR / "csvjson")

SOURCE_URL     = "https://nsearchives.nseindia.com/content/equities/symbolchange.csv"
CSV_FILENAME   = "symbolchange.csv"
JSON_FILENAME  = "symbolchange.json"
YEAR_FILTER_MIN = 2022
REQUEST_TIMEOUT = 30
MAX_RETRIES     = 3
RETRY_DELAY     = 2

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/csv,*/*;q=0.8",
    "Connection": "keep-alive",
}


def download_csv(url, output_path):
    if not REQUESTS_AVAILABLE:
        return False, "requests library not installed"
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return True, "Download successful"
            else:
                message = f"HTTP {response.status_code}"
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return False, message
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            return False, str(e)
    return False, "Max retries exceeded"


def parse_date_year(date_str):
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(date_str, fmt).year
        except ValueError:
            continue
    match = re.search(r'(19|20)\d{2}', date_str)
    return int(match.group()) if match else None


def convert_csv_to_json(csv_path, json_path, year_filter):
    records = []
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            def get_val(keys):
                for k in keys:
                    if k in row:
                        return row[k]
                return ''
            old_symbol  = get_val(['SM_KEY_SYMBOL', 'OLD SYMBOL', 'OLD_SYMBOL']).strip().upper()
            new_symbol  = get_val(['SM_NEW_SYMBOL', 'NEW SYMBOL', 'NEW_SYMBOL']).strip().upper()
            change_date = get_val(['SM_APPLICABLE_FROM', 'DATE', 'APPLICABLE_FROM']).strip()
            if not old_symbol or not new_symbol:
                continue
            if old_symbol in ('SM_KEY_SYMBOL', 'OLD SYMBOL'):
                continue
            year = parse_date_year(change_date)
            if year and year >= year_filter:
                records.append({
                    'SM_KEY_SYMBOL': old_symbol,
                    'SM_NEW_SYMBOL': new_symbol,
                    'SM_APPLICABLE_FROM': change_date,
                    'year': year,
                })
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    return len(records)


def run_symbolchange_download(db_path=None):
    result = {
        'status': 'failed', 'row_count': 0, 'work_remark': '',
        'errors': [], 'warnings': [],
        'detailed_work': {'csv_path': None, 'json_path': None, 'download_time': None},
    }
    if not REQUESTS_AVAILABLE:
        result['errors'].append("requests library not installed. Run: pip install requests")
        result['work_remark'] = "Missing dependency: requests"
        return result

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    except Exception as e:
        result['errors'].append(f"Cannot create output directory: {e}")
        result['work_remark'] = "Directory creation failed"
        return result

    csv_path  = os.path.join(OUTPUT_DIR, CSV_FILENAME)
    json_path = os.path.join(OUTPUT_DIR, JSON_FILENAME)

    start_time = datetime.now()
    success, message = download_csv(SOURCE_URL, csv_path)
    result['detailed_work']['download_time'] = (datetime.now() - start_time).total_seconds()

    if not success:
        result['errors'].append(f"Download failed: {message}")
        result['work_remark'] = f"Download failed: {message}"
        return result
    result['detailed_work']['csv_path'] = csv_path

    try:
        row_count = convert_csv_to_json(csv_path, json_path, YEAR_FILTER_MIN)
        result['detailed_work']['json_path'] = json_path
    except Exception as e:
        result['errors'].append(f"Conversion failed: {e}")
        result['work_remark'] = "CSV to JSON conversion failed"
        return result

    result['status'] = 'success'
    result['row_count'] = row_count
    result['work_remark'] = f"Downloaded and converted {row_count} records (year >= {YEAR_FILTER_MIN})"
    return result


def check_existing_files():
    csv_path  = os.path.join(OUTPUT_DIR, CSV_FILENAME)
    json_path = os.path.join(OUTPUT_DIR, JSON_FILENAME)
    csv_exists  = os.path.exists(csv_path)
    json_exists = os.path.exists(json_path)
    csv_info = json_info = None
    if csv_exists:
        stat = os.stat(csv_path)
        csv_info = {'path': csv_path, 'size': stat.st_size, 'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()}
    if json_exists:
        stat = os.stat(json_path)
        try:
            with open(json_path) as f:
                record_count = len(json.load(f))
        except Exception:
            record_count = 0
        json_info = {'path': json_path, 'size': stat.st_size, 'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(), 'record_count': record_count}
    return {'csv_exists': csv_exists, 'json_exists': json_exists, 'csv_info': csv_info, 'json_info': json_info}
