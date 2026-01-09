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
            conn.execute(
                """
                INSERT INTO metrics (cpu_temp, ambient_temp, fan_rpm, pump_percent)
                VALUES (:cpu_temp, :ambient_temp, :fan_rpm, :pump_percent)
                """,
                DEFAULT_METRICS,
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
