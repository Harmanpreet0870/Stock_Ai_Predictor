# ====================================================
# File Role    : Support File
# File Name    : pipeline_checks.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Pre-pipeline validation — flags, file checks, DB status
# ====================================================

import os
import json
import sqlite3
from pathlib import Path

_SRC_DIR     = Path(__file__).resolve().parent
_CONFIG_DIR  = _SRC_DIR.parent / "config"
_DATA_DIR    = _SRC_DIR.parent.parent.parent.parent / "data"

DATABASE_PATH    = str(_DATA_DIR / "db" / "Nse_Mainbhavdata.db")
CODE_BASE_PATH   = str(_SRC_DIR)
FLAG_POLICY_PATH = str(_CONFIG_DIR / "flag_policy.json")
CONFIG_JSON_PATH = str(_CONFIG_DIR / "pipeline_master.json")

TABLE_NAME = "master_wdate_tb"
FILE_EXTENSION = ".py"

FLAG_ERROR       = -2
FLAG_HOLIDAY     = -1
FLAG_PENDING     =  0
FLAG_DONE        =  1
FLAG_ROLLED_OUT  =  2
VALID_FLAG_VALUES = [FLAG_ERROR, FLAG_HOLIDAY, FLAG_PENDING, FLAG_DONE, FLAG_ROLLED_OUT]

FLAG_DESCRIPTIONS = {
    FLAG_ERROR:      "Error - requires review/retry",
    FLAG_HOLIDAY:    "Holiday - no processing",
    FLAG_PENDING:    "Pending - eligible for execution",
    FLAG_DONE:       "Done - completed successfully",
    FLAG_ROLLED_OUT: "Rolled out - archived",
}


def load_flag_policy():
    try:
        with open(FLAG_POLICY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f"Flag policy file not found: {FLAG_POLICY_PATH}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON in flag policy file: {e}")


def get_component_status():
    try:
        with open(CONFIG_JSON_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        raise Exception(f"Config file not found: {CONFIG_JSON_PATH}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON in config: {e}")

    components = []
    for component in config_data.get('software_components', []):
        components.append({
            'component_id':    component.get('component_id', 'Unknown'),
            'name':            component.get('name', 'Unknown'),
            'enabled':         component.get('enabled', False),
            'execution_order': component.get('execution_order', 0),
            'status':          'Active' if component.get('enabled', False) else 'Inactive',
        })
    active = sum(1 for c in components if c['enabled'])
    return {
        'components': components,
        'summary': {'active': active, 'inactive': len(components) - active, 'total': len(components)},
    }


def validate_files():
    try:
        with open(CONFIG_JSON_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise Exception(f"Config error: {e}")

    files = []
    for component in config_data.get('software_components', []):
        name = component.get('name', 'Unknown')
        full_path = os.path.join(CODE_BASE_PATH, name + FILE_EXTENSION)
        exists = os.path.exists(full_path)
        files.append({
            'component_id': component.get('component_id', 'Unknown'),
            'component_name': name,
            'file_path': full_path,
            'exists': exists,
            'enabled': component.get('enabled', False),
        })

    found   = sum(1 for f in files if f['exists'])
    missing = sum(1 for f in files if not f['exists'])
    missing_enabled = sum(1 for f in files if not f['exists'] and f['enabled'])
    return {
        'files': files,
        'summary': {'found': found, 'missing': missing, 'missing_enabled': missing_enabled, 'total': len(files)},
    }


def get_previous_working_day(db_path=None):
    db = db_path or DATABASE_PATH
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(f"SELECT MAX(wid) FROM {TABLE_NAME}")
    row = cursor.fetchone()
    max_wid = row[0] if row else None
    if max_wid is None:
        conn.close()
        raise Exception(f"No records in {TABLE_NAME}")
    previous_wid = max_wid - 1
    cursor.execute(f"SELECT wid, gdate, tsdate, isholidayflag FROM {TABLE_NAME} WHERE wid = ?", (previous_wid,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise Exception(f"No record for wid={previous_wid}")
    wid, gdate, tsdate, isholidayflag = row
    return {
        'max_wid': max_wid, 'previous_wid': previous_wid,
        'gdate': gdate, 'tsdate': tsdate,
        'isholidayflag': isholidayflag,
        'is_working_day': (isholidayflag == 1),
    }


def check_bhavpip_flag(previous_wid, db_path=None):
    db = db_path or DATABASE_PATH
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT wid, gdate, tsdate, isholidayflag, bhavpip_flag
        FROM {TABLE_NAME} WHERE wid = ?
    """, (previous_wid,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise Exception(f"No record for wid={previous_wid}")
    wid, gdate, tsdate, isholidayflag, bhavpip_flag = row
    result = {
        'previous_wid': previous_wid, 'gdate': gdate, 'tsdate': tsdate,
        'isholidayflag': isholidayflag, 'bhavpip_flag': bhavpip_flag,
        'status': None, 'can_proceed': False, 'message': None,
    }
    if isholidayflag == 1:
        if bhavpip_flag == FLAG_DONE:
            result.update({'status': 'DONE', 'can_proceed': True, 'message': 'Task completed successfully'})
        elif bhavpip_flag == FLAG_PENDING:
            result.update({'status': 'PENDING', 'can_proceed': True, 'message': 'Task not yet executed; eligible for execution'})
        elif bhavpip_flag == FLAG_ERROR:
            result.update({'status': 'ERROR', 'can_proceed': False, 'message': 'Task failed; requires manual review or retry'})
        else:
            result.update({'status': 'UNKNOWN', 'can_proceed': False, 'message': f'Unexpected bhavpip_flag: {bhavpip_flag}'})
    else:
        result.update({'status': 'HOLIDAY', 'can_proceed': False, 'message': f'wid={previous_wid} is holiday/off-day'})
    return result


def validate_execution_allowed(wid, db_path=None):
    db = db_path or DATABASE_PATH
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute(f"SELECT isholidayflag, bhavpip_flag FROM {TABLE_NAME} WHERE wid = ?", (wid,))
        row = cursor.fetchone()
        conn.close()
    except Exception as e:
        return {'allowed': False, 'reason': f"DB error: {e}", 'isholidayflag': None, 'bhavpip_flag': None}

    if row is None:
        return {'allowed': False, 'reason': f"WID {wid} not found", 'isholidayflag': None, 'bhavpip_flag': None}

    isholidayflag, bhavpip_flag = row
    if isholidayflag == 0:
        return {'allowed': False, 'reason': 'Holiday — no processing (isholidayflag=0)', 'isholidayflag': isholidayflag, 'bhavpip_flag': bhavpip_flag}
    if bhavpip_flag == FLAG_DONE:
        return {'allowed': False, 'reason': 'Already completed (flag=1)', 'isholidayflag': isholidayflag, 'bhavpip_flag': bhavpip_flag}
    if bhavpip_flag in (FLAG_PENDING, FLAG_ERROR):
        return {'allowed': True, 'reason': 'Eligible for execution', 'isholidayflag': isholidayflag, 'bhavpip_flag': bhavpip_flag}
    return {'allowed': False, 'reason': f'Unknown flag state: {bhavpip_flag}', 'isholidayflag': isholidayflag, 'bhavpip_flag': bhavpip_flag}


def update_bhavpip_flag(wid, new_flag, error_remark=None, db_path=None):
    if new_flag not in VALID_FLAG_VALUES:
        return {'success': False, 'message': f"Invalid flag value: {new_flag}"}
    db = db_path or DATABASE_PATH
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute(f"SELECT isholidayflag, bhavpip_flag FROM {TABLE_NAME} WHERE wid = ?", (wid,))
        row = cursor.fetchone()
        if row is None:
            conn.close()
            return {'success': False, 'message': f"WID {wid} not found"}
        isholidayflag, current_flag = row
        if isholidayflag == 0:
            conn.close()
            return {'success': False, 'message': "Cannot update — holiday day"}
        if current_flag == FLAG_DONE and new_flag != FLAG_DONE:
            conn.close()
            return {'success': False, 'message': "Already completed, cannot modify"}

        if error_remark and new_flag == FLAG_ERROR:
            cursor.execute(f"UPDATE {TABLE_NAME} SET bhavpip_flag = ?, error_remark = ? WHERE wid = ?",
                           (new_flag, error_remark[:500], wid))
        else:
            cursor.execute(f"UPDATE {TABLE_NAME} SET bhavpip_flag = ?, error_remark = NULL WHERE wid = ?",
                           (new_flag, wid))
        conn.commit()
        conn.close()
        return {'success': True, 'message': f"Flag: {current_flag} → {new_flag}", 'previous_flag': current_flag, 'new_flag': new_flag}
    except Exception as e:
        return {'success': False, 'message': f"DB error: {e}"}


def set_flag_on_success(wid, db_path=None):
    return update_bhavpip_flag(wid, FLAG_DONE, db_path=db_path)


def set_flag_on_error(wid, error_message, db_path=None):
    return update_bhavpip_flag(wid, FLAG_ERROR, error_remark=(error_message or "Unknown error")[:500], db_path=db_path)
