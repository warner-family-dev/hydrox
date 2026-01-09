import json
import threading
import time

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_connection, init_db
from app.services.cpu_fan import read_cpu_fan_rpm
from app.services.fan_metrics import (
    insert_cpu_fan_reading,
    insert_fan_reading,
    recent_cpu_fan_readings,
    recent_fan_readings,
)
from app.services.fans import list_fans, seed_fans_if_empty, sync_fan_count, update_fan_settings
from app.services.git_info import get_git_status
from app.services.liquidctl import get_fan_rpms, set_fan_speed
from app.services.logger import get_logger
from app.services.metrics import (
    DEFAULT_METRICS,
    insert_metrics,
    latest_metrics,
    read_cpu_temp_vcgencmd,
    recent_metrics,
    seed_metrics_if_empty,
)
from app.services.settings import (
    get_active_profile_id,
    get_fan_count,
    seed_settings_if_empty,
    set_active_profile_id,
    set_fan_count,
)

app = FastAPI(title="Hydrox Command Center")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        get_logger().exception("unhandled exception on %s %s", request.method, request.url.path)
        raise


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_settings_if_empty()
    seed_metrics_if_empty()
    seed_fans_if_empty()
    get_logger().info("system startup")
    cpu_thread = threading.Thread(target=_cpu_sampler, daemon=True)
    cpu_thread.start()
    fan_thread = threading.Thread(target=_fan_sampler, daemon=True)
    fan_thread.start()


def _cpu_sampler() -> None:
    while True:
        cpu_temp = read_cpu_temp_vcgencmd()
        if cpu_temp is not None:
            latest = latest_metrics() or {}
            ambient_temp = latest.get("ambient_temp", DEFAULT_METRICS["ambient_temp"])
            fan_rpm = latest.get("fan_rpm", DEFAULT_METRICS["fan_rpm"])
            pump_percent = latest.get("pump_percent", DEFAULT_METRICS["pump_percent"])
            insert_metrics(cpu_temp, ambient_temp, fan_rpm, pump_percent)
        time.sleep(5)


def _fan_sampler() -> None:
    logger = get_logger()
    while True:
        rpms = get_fan_rpms()
        for channel_index, rpm in rpms.items():
            insert_fan_reading(channel_index, rpm)
        cpu_rpm = read_cpu_fan_rpm()
        if cpu_rpm is not None:
            insert_cpu_fan_reading(cpu_rpm)
        else:
            logger.error("cpu fan rpm not found in sysfs")
        time.sleep(5)


@app.get("/", response_class=HTMLResponse)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    metrics = latest_metrics()
    fans = list_fans(active_only=True)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "fans": fans,
        },
    )


@app.get("/profiles", response_class=HTMLResponse)
def profiles(request: Request):
    rows = _load_profiles()
    active_profile_id = get_active_profile_id()
    return templates.TemplateResponse(
        "profiles.html",
        {
            "request": request,
            "profiles": [dict(row) for row in rows],
            "active_profile_id": active_profile_id,
            "error": None,
        },
    )


@app.post("/profiles")
def create_profile(
    name: str = Form(...),
    curve_json: str = Form(...),
    schedule_json: str = Form(""),
):
    error = _validate_profile_json(curve_json, schedule_json)
    if error:
        rows = _load_profiles()
        active_profile_id = get_active_profile_id()
        return templates.TemplateResponse(
            "profiles.html",
            {
                "request": request,
                "profiles": [dict(row) for row in rows],
                "active_profile_id": active_profile_id,
                "error": error,
            },
        )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO profiles (name, curve_json, schedule_json)
            VALUES (?, ?, ?)
            """,
            (name, curve_json, schedule_json or None),
        )
        conn.commit()
    return RedirectResponse("/profiles", status_code=303)


@app.post("/profiles/apply")
def apply_profile(profile_id: int = Form(...)):
    set_active_profile_id(profile_id)
    return RedirectResponse("/profiles", status_code=303)


@app.get("/screens", response_class=HTMLResponse)
def screens(request: Request):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, message_template, font_family, font_size,
                   rotation_seconds, tag, created_at
            FROM screens
            ORDER BY created_at DESC
            """
        ).fetchall()
    return templates.TemplateResponse(
        "screens.html",
        {
            "request": request,
            "screens": [dict(row) for row in rows],
        },
    )


@app.post("/screens")
def create_screen(
    name: str = Form(...),
    message_template: str = Form(...),
    font_family: str = Form("IBM Plex Mono"),
    font_size: int = Form(12),
    rotation_seconds: int = Form(15),
    tag: str = Form(""),
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO screens (name, message_template, font_family, font_size,
                                 rotation_seconds, tag)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, message_template, font_family, font_size, rotation_seconds, tag or None),
        )
        conn.commit()
    return RedirectResponse("/screens", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    branch, commit_date = get_git_status()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "branch": branch,
            "commit_date": commit_date,
        },
    )


@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    fans = list_fans()
    fan_count = get_fan_count()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "fans": fans,
            "fan_count": fan_count,
        },
    )


@app.post("/settings/fans")
def update_fan(fan_id: int = Form(...), name: str = Form(...), max_rpm: str | None = Form(None)):
    parsed_rpm = None
    if max_rpm:
        try:
            parsed_rpm = int(max_rpm)
        except ValueError:
            parsed_rpm = None
    update_fan_settings(fan_id, name, parsed_rpm)
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/fan-count")
def update_fan_count(fan_count: int = Form(...)):
    set_fan_count(fan_count)
    sync_fan_count(get_fan_count())
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/fans/calibrate")
def calibrate_fans():
    logger = get_logger()
    fans = list_fans(active_only=True)
    for fan in fans:
        set_fan_speed(fan["channel_index"], 100)
    time.sleep(15)
    rpms = get_fan_rpms()
    if not rpms:
        logger.error("no fan rpms found during calibration")
    for channel_index, rpm in rpms.items():
        _update_fan_max_rpm(channel_index, rpm)
    _restore_after_calibration(fans)
    logger.info("fan calibration completed")
    return RedirectResponse("/settings", status_code=303)


@app.post("/api/metrics/ingest")
def ingest_metrics(
    cpu_temp: float = Form(...),
    ambient_temp: float = Form(...),
    fan_rpm: int = Form(...),
    pump_percent: int = Form(...),
):
    insert_metrics(cpu_temp, ambient_temp, fan_rpm, pump_percent)
    return JSONResponse({"status": "ok"})


@app.get("/api/metrics/latest")
def get_latest_metrics():
    return JSONResponse(latest_metrics() or {})


@app.get("/api/metrics/recent")
def get_recent_metrics(limit: int = 24):
    return JSONResponse(recent_metrics(limit=limit))


@app.get("/api/fans/percent")
def get_fan_percent(limit: int = 24):
    fans = list_fans(active_only=True)
    max_rpm_map = {fan["channel_index"]: fan["max_rpm"] for fan in fans if fan["max_rpm"]}
    fan_series = _fan_series_from_readings(limit, max_rpm_map)
    cpu_series = _cpu_fan_series(limit, max_rpm=8000)
    pump_series = _pump_series(limit)
    return JSONResponse(
        {
            "series": {
                **fan_series,
                "cpu_fan": cpu_series,
                "pump": pump_series,
            }
        }
    )


def _load_profiles():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, curve_json, schedule_json, created_at
            FROM profiles
            ORDER BY created_at DESC
            """
        ).fetchall()
        return rows


def _update_fan_max_rpm(channel_index: int, rpm: int) -> None:
    from app.services.fans import update_fan_max_rpm

    update_fan_max_rpm(channel_index, rpm)


def _restore_after_calibration(fans: list[dict]) -> None:
    logger = get_logger()
    active_profile_id = get_active_profile_id()
    if active_profile_id is None:
        for fan in fans:
            set_fan_speed(fan["channel_index"], 20)
        return
    profile = _load_profile(active_profile_id)
    if not profile:
        logger.error("active profile %s not found, defaulting to 20%%", active_profile_id)
        for fan in fans:
            set_fan_speed(fan["channel_index"], 20)
        return
    cpu_temp = read_cpu_temp_vcgencmd()
    if cpu_temp is None:
        logger.error("cpu temp unavailable, defaulting to 20%%")
        for fan in fans:
            set_fan_speed(fan["channel_index"], 20)
        return
    speeds = _fan_speeds_from_profile(profile["curve_json"], cpu_temp, fans)
    for fan in fans:
        speed = speeds.get(fan["channel_index"], 20)
        set_fan_speed(fan["channel_index"], speed)


def _load_profile(profile_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, curve_json
            FROM profiles
            WHERE id = ?
            """,
            (profile_id,),
        ).fetchone()
        return dict(row) if row else None


def _fan_speeds_from_profile(curve_json: str, temp: float, fans: list[dict]) -> dict[int, int]:
    logger = get_logger()
    try:
        curve = json.loads(curve_json)
    except json.JSONDecodeError:
        logger.error("invalid profile curve json")
        return {}
    speeds = {}
    for fan in fans:
        key = f"fan_{fan['channel_index']}"
        points = curve.get(key)
        if not points:
            continue
        points = sorted(points, key=lambda item: item["temp"])
        speeds[fan["channel_index"]] = int(_interpolate(points, temp))
    return speeds


def _interpolate(points: list[dict], temp: float) -> float:
    if temp <= points[0]["temp"]:
        return points[0]["fan"]
    if temp >= points[-1]["temp"]:
        return points[-1]["fan"]
    for lower, upper in zip(points, points[1:]):
        if lower["temp"] <= temp <= upper["temp"]:
            span = upper["temp"] - lower["temp"]
            if span <= 0:
                return lower["fan"]
            ratio = (temp - lower["temp"]) / span
            return lower["fan"] + ratio * (upper["fan"] - lower["fan"])
    return points[-1]["fan"]


def _fan_series_from_readings(limit: int, max_rpm_map: dict[int, int]) -> dict[str, list[float]]:
    readings = recent_fan_readings(limit)
    grouped: dict[int, list[int]] = {}
    for row in reversed(readings):
        grouped.setdefault(row["channel_index"], []).append(row["rpm"])
    series: dict[str, list[float]] = {}
    for channel_index, max_rpm in max_rpm_map.items():
        rpms = grouped.get(channel_index, [])[-limit:]
        if not rpms:
            continue
        series[f"fan_{channel_index}"] = [min((rpm / max_rpm) * 100, 100) for rpm in rpms]
    return series


def _cpu_fan_series(limit: int, max_rpm: int) -> list[float]:
    readings = recent_cpu_fan_readings(limit)
    rpms = [row["rpm"] for row in reversed(readings)]
    return [min((rpm / max_rpm) * 100, 100) for rpm in rpms]


def _pump_series(limit: int) -> list[float]:
    rows = recent_metrics(limit=limit)
    return [row["pump_percent"] for row in rows]


def _validate_profile_json(curve_json: str, schedule_json: str) -> str | None:
    try:
        curve = json.loads(curve_json)
    except json.JSONDecodeError:
        return "Curve JSON must be valid JSON."

    if not isinstance(curve, dict) or not curve:
        return "Curve JSON must be an object with per-fan entries."

    for channel, points in curve.items():
        if not isinstance(points, list) or not points:
            return f"Curve for {channel} must be a non-empty list."
        for point in points:
            if not isinstance(point, dict):
                return f"Curve point for {channel} must be an object."
            if "temp" not in point or "fan" not in point:
                return f"Curve point for {channel} must include temp and fan."
            if not isinstance(point["temp"], (int, float)):
                return f"Curve temp for {channel} must be a number."
            if not isinstance(point["fan"], (int, float)):
                return f"Curve fan for {channel} must be a number."
            if not 0 <= float(point["fan"]) <= 100:
                return f"Curve fan for {channel} must be 0-100."

    if schedule_json:
        try:
            schedule = json.loads(schedule_json)
        except json.JSONDecodeError:
            return "Schedule JSON must be valid JSON."
        if not isinstance(schedule, dict):
            return "Schedule JSON must be an object."
        if "cron" in schedule and not isinstance(schedule["cron"], str):
            return "Schedule cron must be a string."
        if "window" in schedule:
            window = schedule["window"]
            if not isinstance(window, dict):
                return "Schedule window must be an object."
            if "days" in window and not isinstance(window["days"], list):
                return "Schedule window days must be a list."
            if "start" in window and not isinstance(window["start"], str):
                return "Schedule window start must be a string."
            if "end" in window and not isinstance(window["end"], str):
                return "Schedule window end must be a string."

    return None
