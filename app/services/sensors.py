import glob
from pathlib import Path

from app.db import get_connection
from app.services.liquidctl import get_liquid_temps
from app.services.logger import get_logger

DEFAULT_UNIT = "C"


def seed_sensors_if_empty() -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM sensors").fetchone()
        if row["count"] > 0:
            return
    _seed_liquid_sensors()
    _seed_ds18b20_sensors()


def sync_ds18b20_sensors() -> None:
    discovered = _discover_ds18b20_ids()
    if not discovered:
        return
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT source_id FROM sensors WHERE kind = 'ds18b20'"
        ).fetchall()
        existing_ids = {row["source_id"] for row in existing}
        new_ids = [sensor_id for sensor_id in discovered if sensor_id not in existing_ids]
        for sensor_id in new_ids:
            default_name = f"DS18B20 {sensor_id}"
            conn.execute(
                """
                INSERT INTO sensors (kind, source_id, name, default_name, unit)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("ds18b20", sensor_id, default_name, default_name, DEFAULT_UNIT),
            )
        if new_ids:
            conn.commit()


def list_sensors() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, kind, source_id, name, default_name, unit, active
            FROM sensors
            ORDER BY kind, source_id
            """
        ).fetchall()
        return [dict(row) for row in rows]


def update_sensor_settings(sensor_id: int, name: str, unit: str) -> None:
    normalized = unit.upper() if unit else DEFAULT_UNIT
    if normalized not in ("C", "F"):
        normalized = DEFAULT_UNIT
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE sensors
            SET name = ?, unit = ?
            WHERE id = ?
            """,
            (name, normalized, sensor_id),
        )
        conn.commit()


def latest_sensor_readings() -> dict[int, float]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT sensor_id, temp_c
            FROM sensor_readings
            WHERE id IN (
                SELECT MAX(id) FROM sensor_readings GROUP BY sensor_id
            )
            """
        ).fetchall()
        return {row["sensor_id"]: row["temp_c"] for row in rows}


def insert_sensor_reading(sensor_id: int, temp_c: float) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sensor_readings (sensor_id, temp_c)
            VALUES (?, ?)
            """,
            (sensor_id, temp_c),
        )
        conn.commit()


def read_ds18b20_temps() -> dict[str, float]:
    temps: dict[str, float] = {}
    for device_path in _discover_ds18b20_paths():
        sensor_id = device_path.name
        temp = _read_ds18b20_temp(device_path)
        if temp is not None:
            temps[sensor_id] = temp
    return temps


def format_temp(temp_c: float, unit: str) -> str:
    if unit.upper() == "F":
        value = temp_c * 9 / 5 + 32
        return f"{value:.1f}°F"
    return f"{temp_c:.1f}°C"


def _seed_liquid_sensors() -> None:
    with get_connection() as conn:
        for index in (1, 2):
            name = f"Liquid Temp {index}"
            source_id = f"liquid_temp_{index}"
            conn.execute(
                """
                INSERT OR IGNORE INTO sensors (kind, source_id, name, default_name, unit)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("liquidctl", source_id, name, name, DEFAULT_UNIT),
            )
        conn.commit()


def _seed_ds18b20_sensors() -> None:
    discovered = _discover_ds18b20_ids()
    if not discovered:
        return
    with get_connection() as conn:
        for sensor_id in discovered:
            default_name = f"DS18B20 {sensor_id}"
            conn.execute(
                """
                INSERT OR IGNORE INTO sensors (kind, source_id, name, default_name, unit)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("ds18b20", sensor_id, default_name, default_name, DEFAULT_UNIT),
            )
        conn.commit()


def _discover_ds18b20_paths() -> list[Path]:
    return [Path(path) for path in glob.glob("/sys/bus/w1/devices/28-*")]


def _discover_ds18b20_ids() -> list[str]:
    return [path.name for path in _discover_ds18b20_paths()]


def _read_ds18b20_temp(path: Path) -> float | None:
    try:
        content = path.joinpath("w1_slave").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in content.splitlines():
        if "t=" in line:
            try:
                value = float(line.split("t=", 1)[1].strip())
                return value / 1000.0
            except ValueError:
                return None
    return None


def refresh_liquid_sensors() -> dict[str, float]:
    temps = get_liquid_temps()
    results: dict[str, float] = {}
    for index, value in enumerate(temps[:2], start=1):
        results[f"liquid_temp_{index}"] = value
    if not results:
        get_logger().error("liquidctl status returned no temperatures")
    return results
