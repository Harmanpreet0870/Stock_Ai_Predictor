# ====================================================
# File Role    : Support File
# File Name    : tempbhav_to_master.py
# Location     : backend/bhavpipeline/src/
# Purpose      : Transfer validated data from tempbhav_tb to bhavdata_master_tb
# ====================================================

import sqlite3

TABLE_TEMPBHAV       = "tempbhav_tb"
TABLE_BHAVDATA_MASTER = "bhavdata_master_tb"
TABLE_MASTER_WDATE   = "master_wdate_tb"

TRANSFER_COLUMNS = [
    "msid", "symbol", "series", "date1", "tsdate", "prev_close", "open_price",
    "high_price", "low_price", "last_price", "close_price", "avg_price",
    "ttl_trd_qnty", "turnover_lacs", "no_of_trades", "deliv_qty",
    "deliv_per", "perc_change", "trg",
]


def run_tempbhav_to_master(tsdate, wid, db_path):
    result = {
        'status': 'failed', 'row_count': 0, 'work_remark': '',
        'errors': [], 'warnings': [],
        'detailed_work': {'staging_count': 0, 'master_count': 0, 'previous_deleted': 0},
    }

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_TEMPBHAV} WHERE tsdate = ?", (tsdate,))
        staging_count = cursor.fetchone()[0]
        result['detailed_work']['staging_count'] = staging_count

        if staging_count == 0:
            result['errors'].append(f"No data in {TABLE_TEMPBHAV} for tsdate={tsdate}")
            result['work_remark'] = "No staging data found"
            return result

        cursor.execute("BEGIN TRANSACTION")
        columns_str = ", ".join(TRANSFER_COLUMNS)
        cursor.execute(f"""
            INSERT INTO {TABLE_BHAVDATA_MASTER} ({columns_str})
            SELECT {columns_str} FROM {TABLE_TEMPBHAV} WHERE tsdate = ?
        """, (tsdate,))

        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_BHAVDATA_MASTER} WHERE tsdate = ?", (tsdate,))
        master_count = cursor.fetchone()[0]
        result['detailed_work']['master_count'] = master_count

        if staging_count != master_count:
            raise Exception(f"Row count mismatch: staging={staging_count}, master={master_count}")

        cursor.execute(f"""
            UPDATE {TABLE_MASTER_WDATE}
            SET bhavupdator_flag = 1,
                tmpbhvupd_count  = ?,
                bhavupd_count    = ?,
                bhavdatarow_count = ?,
                error_remark     = NULL
            WHERE wid = ?
        """, (staging_count, staging_count, master_count, wid))

        # Delete previous day's staging data
        cursor.execute(f"SELECT MAX(tsdate) FROM {TABLE_TEMPBHAV} WHERE tsdate < ?", (tsdate,))
        prev_row = cursor.fetchone()
        previous_tsdate = prev_row[0] if prev_row and prev_row[0] else None
        if previous_tsdate:
            cursor.execute(f"DELETE FROM {TABLE_TEMPBHAV} WHERE tsdate = ?", (previous_tsdate,))
            result['detailed_work']['previous_deleted'] = cursor.rowcount

        conn.commit()

        result['status'] = 'success'
        result['row_count'] = master_count
        result['work_remark'] = f"Transferred {master_count} rows to master"
        if previous_tsdate:
            result['work_remark'] += f", deleted {result['detailed_work']['previous_deleted']} staging rows"

    except Exception as e:
        if conn:
            conn.rollback()
        try:
            err_conn = sqlite3.connect(db_path)
            err_conn.execute(f"""
                UPDATE {TABLE_MASTER_WDATE} SET bhavupdator_flag = -2, error_remark = ? WHERE wid = ?
            """, (str(e)[:200], wid))
            err_conn.commit()
            err_conn.close()
        except Exception:
            pass
        result['errors'].append(str(e))
        result['work_remark'] = f"Transfer failed: {e}"

    finally:
        if conn:
            conn.close()

    return result


def find_pending_transfer_date(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT wid, tsdate FROM {TABLE_MASTER_WDATE}
            WHERE tmpbhvupd_flag IN (1, -2) AND bhavupdator_flag = 0
            ORDER BY wid ASC LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return (row[0], row[1]) if row else (None, None)
    except Exception as e:
        print(f"Error finding pending transfer date: {e}")
        return None, None
