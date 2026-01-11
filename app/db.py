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
                title_template TEXT,
                value_template TEXT,
                font_family TEXT NOT NULL,
                title_font_family TEXT,
                value_font_family TEXT,
                font_size INTEGER NOT NULL,
                title_font_size INTEGER,
                value_font_size INTEGER,
                brightness_percent INTEGER NOT NULL DEFAULT 100,
                rotation_seconds INTEGER NOT NULL,
                tag TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oled_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                oled_channel INTEGER NOT NULL,
                screen_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(oled_channel, screen_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fan_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_index INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                default_name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                max_rpm INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fan_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_index INTEGER NOT NULL,
                rpm INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cpu_fan_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rpm INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                source_id TEXT NOT NULL,
                name TEXT NOT NULL,
                default_name TEXT NOT NULL,
                unit TEXT NOT NULL DEFAULT 'C',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(kind, source_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id INTEGER NOT NULL,
                temp_c REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_column(conn, "fan_channels", "active", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "fan_channels", "max_rpm", "INTEGER")
        _ensure_column(conn, "screens", "title_template", "TEXT")
        _ensure_column(conn, "screens", "value_template", "TEXT")
        _ensure_column(conn, "screens", "title_font_family", "TEXT")
        _ensure_column(conn, "screens", "value_font_family", "TEXT")
        _ensure_column(conn, "screens", "title_font_size", "INTEGER")
        _ensure_column(conn, "screens", "value_font_size", "INTEGER")
        _ensure_column(conn, "screens", "brightness_percent", "INTEGER NOT NULL DEFAULT 100")
        _ensure_column(conn, "sensors", "unit", "TEXT NOT NULL DEFAULT 'C'")
        _ensure_column(conn, "sensors", "active", "INTEGER NOT NULL DEFAULT 1")
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    column_names = {row[1] for row in columns}
    if column not in column_names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
