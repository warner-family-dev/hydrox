from app.db import get_connection

FAN_COUNT_KEY = "fan_count"
ACTIVE_PROFILE_KEY = "active_profile_id"
DEFAULT_FAN_COUNT = 7
PUMP_CHANNEL_KEY = "pump_channel"
DEFAULT_PROFILE_KEY = "default_profile_id"


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


def get_active_profile_id() -> int | None:
    value = get_setting(ACTIVE_PROFILE_KEY)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_active_profile_id(profile_id: int | None) -> None:
    if profile_id is None:
        set_setting(ACTIVE_PROFILE_KEY, "")
        return
    set_setting(ACTIVE_PROFILE_KEY, str(profile_id))


def get_default_profile_id() -> int | None:
    value = get_setting(DEFAULT_PROFILE_KEY)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_default_profile_id(profile_id: int | None) -> None:
    if profile_id is None:
        set_setting(DEFAULT_PROFILE_KEY, "")
        return
    set_setting(DEFAULT_PROFILE_KEY, str(profile_id))


def get_pump_channel() -> int | None:
    value = get_setting(PUMP_CHANNEL_KEY)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_pump_channel(channel_index: int | None) -> None:
    if channel_index is None:
        set_setting(PUMP_CHANNEL_KEY, "")
        return
    set_setting(PUMP_CHANNEL_KEY, str(channel_index))


def get_fan_pwm(channel_index: int) -> int | None:
    value = get_setting(f"fan_pwm_{channel_index}")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_fan_pwm(channel_index: int, percent: int) -> None:
    set_setting(f"fan_pwm_{channel_index}", str(percent))
