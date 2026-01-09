from app.db import get_connection

FAN_COUNT_KEY = "fan_count"
DEFAULT_FAN_COUNT = 7


def seed_settings_if_empty() -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM settings").fetchone()
        if row["count"] == 0:
            conn.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                """,
                (FAN_COUNT_KEY, str(DEFAULT_FAN_COUNT)),
            )
            conn.commit()


def get_setting(key: str, fallback: str | None = None) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT value FROM settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
        return row["value"] if row else fallback


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def get_fan_count() -> int:
    value = get_setting(FAN_COUNT_KEY, str(DEFAULT_FAN_COUNT))
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_FAN_COUNT


def set_fan_count(count: int) -> None:
    set_setting(FAN_COUNT_KEY, str(max(1, count)))
