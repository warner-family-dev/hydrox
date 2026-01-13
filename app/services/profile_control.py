from __future__ import annotations

import json
import time
from collections import defaultdict

from app.db import get_connection
from app.services.fans import list_fans
from app.services.liquidctl import set_fan_speed
from app.services.logger import get_logger
from app.services.manual_override import is_overridden
from app.services.metrics import read_cpu_temp_vcgencmd
from app.services.pump_curve import (
    PUMP_MAX_RPM,
    PUMP_MIN_RPM,
    percent_to_rpm,
    pump_pwm_for_rpm,
    pump_rpm_for_pwm,
)
from app.services.sensors import latest_sensor_readings, list_sensors
from app.services.settings import get_active_profile_id, get_fan_pwm, get_pump_channel, set_fan_pwm


_SENSOR_HISTORY: dict[str, list[tuple[float, float]]] = defaultdict(list)
_OUTPUT_HISTORY: dict[int, list[tuple[float, float]]] = defaultdict(list)


def run_profile_loop() -> None:
    logger = get_logger()
    while True:
        profile = _load_active_profile()
        if not profile:
            time.sleep(5)
            continue
        settings = profile.get("settings", {})
        sensor_window = _read_int(settings.get("sensor_smoothing_sec"), fallback=0)
        sleep_seconds = max(1, sensor_window or 5)
        try:
            _apply_profile(profile)
        except Exception:
            logger.exception("profile control loop failed")
        time.sleep(sleep_seconds)


def _apply_profile(profile: dict) -> None:
    targets = _compute_targets(profile)
    for channel_index, percent in targets.items():
        if percent is None:
            continue
        if not set_fan_speed(channel_index, int(percent)):
            continue
        set_fan_pwm(channel_index, int(percent))


def compute_profile_target_for_channel(channel_index: int) -> int | None:
    profile = _load_active_profile()
    if not profile:
        return None
    targets = _compute_targets(profile)
    return targets.get(channel_index)


def _load_active_profile() -> dict | None:
    profile_id = get_active_profile_id()
    if profile_id is None:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT curve_json
            FROM profiles
            WHERE id = ?
            """,
            (profile_id,),
        ).fetchone()
    if not row:
        return None
    try:
        curve = json.loads(row["curve_json"])
    except json.JSONDecodeError:
        return None
    if not isinstance(curve, dict):
        return None
    if "rules" not in curve:
        return _convert_legacy_curve(curve)
    return curve


def _convert_legacy_curve(curve: dict) -> dict:
    rules = []
    for key, points in curve.items():
        if not key.startswith("fan_"):
            continue
        try:
            channel = int(key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        rules.append({"sensor_id": "cpu", "fan_channels": [channel], "points": points})
    return {"rules": rules, "settings": {}}


def _compute_targets(profile: dict) -> dict[int, int | None]:
    settings = profile.get("settings", {}) if isinstance(profile, dict) else {}
    sensor_window = _read_int(settings.get("sensor_smoothing_sec"), fallback=0)
    fan_window = _read_int(settings.get("fan_smoothing_sec"), fallback=0)
    pump_window = _read_int(settings.get("pump_smoothing_sec"), fallback=0)
    fan_rate = _read_int(settings.get("fan_rate_limit_rpm"), fallback=0)
    pump_rate = _read_int(settings.get("pump_rate_limit_rpm"), fallback=0)
    sensor_min = _read_float(settings.get("sensor_min_c"))
    sensor_max = _read_float(settings.get("sensor_max_c"))
    fallback_map = settings.get("fallback_map", {}) if isinstance(settings.get("fallback_map", {}), dict) else {}

    fans = list_fans(active_only=True)
    max_rpm_map = {fan["channel_index"]: fan.get("max_rpm") for fan in fans}
    pump_channel = get_pump_channel()

    sensor_values = _get_sensor_values(sensor_window)

    targets: dict[int, int | None] = {}
    rules = profile.get("rules", []) if isinstance(profile.get("rules", []), list) else []
    for rule in rules:
        sensor_id = rule.get("sensor_id")
        fan_channels = rule.get("fan_channels", [])
        points = rule.get("points", [])
        if not sensor_id or not isinstance(fan_channels, list) or not isinstance(points, list):
            continue
        sensor_value = _resolve_sensor_value(sensor_id, sensor_values, fallback_map)
        if sensor_value is None:
            continue
        if sensor_id != "cpu" and _sensor_out_of_bounds(sensor_value, sensor_min, sensor_max):
            continue
        target_percent = _interpolate(points, sensor_value)
        if target_percent is None:
            continue
        for channel_index in fan_channels:
            try:
                channel = int(channel_index)
            except (TypeError, ValueError):
                continue
            if is_overridden(channel):
                continue
            is_pump = pump_channel is not None and channel == pump_channel
            targets[channel] = _apply_output_controls(
                channel,
                target_percent,
                is_pump,
                max_rpm_map.get(channel),
                fan_rate,
                pump_rate,
                fan_window,
                pump_window,
            )
    return targets


def _apply_output_controls(
    channel_index: int,
    target_percent: float,
    is_pump: bool,
    max_rpm: int | None,
    fan_rate: int,
    pump_rate: int,
    fan_window: int,
    pump_window: int,
) -> int | None:
    now = time.time()
    target_percent = max(0.0, min(100.0, float(target_percent)))
    if is_pump:
        smoothed = _apply_smoothing(_OUTPUT_HISTORY, channel_index, target_percent, pump_window, now)
        desired_rpm = percent_to_rpm(int(round(smoothed)), PUMP_MAX_RPM, PUMP_MIN_RPM)
        current_pwm = get_fan_pwm(channel_index) or 0
        current_rpm = pump_rpm_for_pwm(current_pwm) or 0
        limited_rpm = _apply_rate_limit(current_rpm, desired_rpm, pump_rate)
        pwm = pump_pwm_for_rpm(limited_rpm)
        if pwm is None:
            return None
        return int(max(0, min(100, pwm)))

    if not max_rpm:
        return None
    smoothed = _apply_smoothing(_OUTPUT_HISTORY, channel_index, target_percent, fan_window, now)
    desired_rpm = int(round(max_rpm * smoothed / 100))
    current_pwm = get_fan_pwm(channel_index) or 0
    current_rpm = int(round(max_rpm * current_pwm / 100))
    limited_rpm = _apply_rate_limit(current_rpm, desired_rpm, fan_rate)
    percent = int(round(max(0, min(100, limited_rpm / max_rpm * 100))))
    return percent


def _apply_rate_limit(current_rpm: int, target_rpm: int, limit_rpm: int) -> int:
    if limit_rpm <= 0:
        return target_rpm
    delta = target_rpm - current_rpm
    if abs(delta) <= limit_rpm:
        return target_rpm
    return current_rpm + (limit_rpm if delta > 0 else -limit_rpm)


def _apply_smoothing(history: dict, key: int | str, value: float, window_sec: int, now: float) -> float:
    if window_sec <= 0:
        return value
    items = history[key]
    items.append((now, value))
    cutoff = now - window_sec
    while items and items[0][0] < cutoff:
        items.pop(0)
    if not items:
        return value
    return sum(item[1] for item in items) / len(items)


def _get_sensor_values(window_sec: int) -> dict[str, float]:
    values: dict[str, float] = {}
    now = time.time()
    cpu_temp = read_cpu_temp_vcgencmd()
    if cpu_temp is not None:
        values["cpu"] = _apply_smoothing(_SENSOR_HISTORY, "cpu", cpu_temp, window_sec, now)
    readings = latest_sensor_readings()
    for sensor in list_sensors():
        sensor_id = str(sensor["id"])
        temp_c = readings.get(sensor["id"])
        if temp_c is None:
            continue
        values[sensor_id] = _apply_smoothing(_SENSOR_HISTORY, sensor_id, temp_c, window_sec, now)
    return values


def _resolve_sensor_value(sensor_id: str | int, values: dict[str, float], fallback_map: dict) -> float | None:
    key = str(sensor_id)
    if key in values:
        return values[key]
    fallback = fallback_map.get(key)
    if fallback is None:
        return None
    fallback_key = str(fallback)
    return values.get(fallback_key)


def _sensor_out_of_bounds(value: float, minimum: float | None, maximum: float | None) -> bool:
    if minimum is not None and value < minimum:
        return True
    if maximum is not None and value > maximum:
        return True
    return False


def _interpolate(points: list[dict], temp: float) -> float | None:
    if not points:
        return None
    cleaned = []
    for point in points:
        if not isinstance(point, dict):
            continue
        if "temp" not in point or "fan" not in point:
            continue
        try:
            cleaned.append({"temp": float(point["temp"]), "fan": float(point["fan"])})
        except (TypeError, ValueError):
            continue
    if not cleaned:
        return None
    cleaned.sort(key=lambda item: item["temp"])
    if temp <= cleaned[0]["temp"]:
        return cleaned[0]["fan"]
    if temp >= cleaned[-1]["temp"]:
        return cleaned[-1]["fan"]
    for lower, upper in zip(cleaned, cleaned[1:]):
        if lower["temp"] <= temp <= upper["temp"]:
            span = upper["temp"] - lower["temp"]
            if span <= 0:
                return lower["fan"]
            ratio = (temp - lower["temp"]) / span
            return lower["fan"] + ratio * (upper["fan"] - lower["fan"])
    return cleaned[-1]["fan"]


def _read_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _read_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
