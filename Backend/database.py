import sqlite3
from contextlib import contextmanager
from paths import MAIN_DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(MAIN_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(zip(row.keys(), row))
