import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_ENV = "HYDROX_DB_PATH"
DEFAULT_DB = "/data/hydrox.db"


def db_path() -> str:
    return os.getenv(DB_ENV, DEFAULT_DB)


@contextmanager
def get_connection():
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpu_temp REAL,
                ambient_temp REAL,
                fan_rpm INTEGER,
                pump_percent INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                curve_json TEXT NOT NULL,
                schedule_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS screens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message_template TEXT NOT NULL,
                font_family TEXT NOT NULL,
                font_size INTEGER NOT NULL,
                rotation_seconds INTEGER NOT NULL,
                tag TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
