from app.db import get_connection


def insert_fan_reading(channel_index: int, rpm: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO fan_readings (channel_index, rpm)
            VALUES (?, ?)
            """,
            (channel_index, rpm),
        )
        conn.commit()


def insert_cpu_fan_reading(rpm: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cpu_fan_readings (rpm)
            VALUES (?)
            """,
            (rpm,),
        )
        conn.commit()


def recent_fan_readings(limit: int = 24):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT channel_index, rpm, created_at
            FROM fan_readings
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit * 8,),
        ).fetchall()
        return [dict(row) for row in rows]


def recent_cpu_fan_readings(limit: int = 24):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT rpm, created_at
            FROM cpu_fan_readings
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def latest_fan_readings():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT channel_index, rpm, MAX(created_at) AS created_at
            FROM fan_readings
            GROUP BY channel_index
            """
        ).fetchall()
        return [dict(row) for row in rows]
