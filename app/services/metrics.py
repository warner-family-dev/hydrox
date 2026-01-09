import subprocess
from typing import Optional

from app.db import get_connection


DEFAULT_METRICS = {
    "cpu_temp": 43.2,
    "ambient_temp": 18.7,
    "fan_rpm": 950,
    "pump_percent": 42,
}


def seed_metrics_if_empty() -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM metrics").fetchone()
        if row["count"] == 0:
            samples = [
                {"cpu_temp": 41.0, "ambient_temp": 17.8, "fan_rpm": 880, "pump_percent": 38},
                {"cpu_temp": 41.6, "ambient_temp": 18.0, "fan_rpm": 900, "pump_percent": 39},
                {"cpu_temp": 42.1, "ambient_temp": 18.1, "fan_rpm": 910, "pump_percent": 40},
                {"cpu_temp": 42.4, "ambient_temp": 18.2, "fan_rpm": 920, "pump_percent": 40},
                {"cpu_temp": 42.9, "ambient_temp": 18.4, "fan_rpm": 930, "pump_percent": 41},
                {"cpu_temp": 43.2, "ambient_temp": 18.5, "fan_rpm": 940, "pump_percent": 41},
                {"cpu_temp": 43.5, "ambient_temp": 18.6, "fan_rpm": 950, "pump_percent": 42},
                {"cpu_temp": 43.1, "ambient_temp": 18.7, "fan_rpm": 960, "pump_percent": 42},
                {"cpu_temp": 42.8, "ambient_temp": 18.6, "fan_rpm": 955, "pump_percent": 41},
                {"cpu_temp": 42.4, "ambient_temp": 18.5, "fan_rpm": 945, "pump_percent": 41},
                {"cpu_temp": 42.0, "ambient_temp": 18.3, "fan_rpm": 930, "pump_percent": 40},
                DEFAULT_METRICS,
            ]
            conn.executemany(
                """
                INSERT INTO metrics (cpu_temp, ambient_temp, fan_rpm, pump_percent)
                VALUES (:cpu_temp, :ambient_temp, :fan_rpm, :pump_percent)
                """,
                samples,
            )
            conn.commit()


def latest_metrics():
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT cpu_temp, ambient_temp, fan_rpm, pump_percent, created_at
            FROM metrics
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None


def recent_metrics(limit: int = 12):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cpu_temp, ambient_temp, fan_rpm, pump_percent, created_at
            FROM metrics
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]


def insert_metrics(cpu_temp: float, ambient_temp: float, fan_rpm: int, pump_percent: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO metrics (cpu_temp, ambient_temp, fan_rpm, pump_percent)
            VALUES (?, ?, ?, ?)
            """,
            (cpu_temp, ambient_temp, fan_rpm, pump_percent),
        )
        conn.commit()


def read_cpu_temp_vcgencmd() -> Optional[float]:
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if "=" not in raw:
        return None
    value = raw.split("=", 1)[1].replace("'C", "").strip()
    try:
        return float(value)
    except ValueError:
        return None
