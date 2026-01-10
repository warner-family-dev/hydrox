import json
import threading
import time

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_connection, init_db
from app.services.fan_metrics import (
    latest_fan_readings,
    recent_cpu_fan_readings,
    recent_fan_readings,
)
from app.services.fans import list_fans, seed_fans_if_empty, sync_fan_count, update_fan_settings
from app.services.git_info import get_git_status
from app.services.liquidctl import set_fan_speed
from app.services.logger import get_logger, now_local
from app.services.metrics import (
    latest_metrics,
    recent_metrics,
    seed_metrics_if_empty,
)
from app.services.oled import list_font_choices, list_oled_channels
from app.services.oled_manager import PlaylistScreen, list_token_definitions, start_oled_job, stop_oled_job
from app.services.sensors import (
    format_temp,
    latest_sensor_readings,
    list_sensors,
    recent_sensor_readings,
    seed_sensors_if_empty,
    update_sensor_settings,
)
from app.services.settings import (
    get_active_profile_id,
    get_fan_count,
    seed_settings_if_empty,
    set_active_profile_id,
    set_fan_count,
)
from app.services.daemon import start_daemon
from app.services.system_status import get_status_payload, set_image_start_time

app = FastAPI(title="Hydrox Command Center")

_cpu_fan_missing_logged = False
_calibration_lock = threading.Lock()
_calibration_state = {
    "running": False,
    "phase": "idle",
    "started_at": 0.0,
    "restore_started_at": 0.0,
    "completed_at": 0.0,
}
_CALIBRATION_SECONDS = 20
_RESTORE_GRACE_SECONDS = 5

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
    set_image_start_time(time.time())
    init_db()
    seed_settings_if_empty()
    seed_metrics_if_empty()
    seed_fans_if_empty()
    seed_sensors_if_empty()
    branch, _ = get_git_status()
    logger = get_logger()
    logger.info("#######")
    logger.info(
        "System has been started - current boot time is %s and code version is %s",
        now_local(),
        branch,
    )
    logger.info("#######")
    start_daemon()


@app.get("/", response_class=HTMLResponse)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    metrics = latest_metrics()
    fans = list_fans(active_only=True)
    sensors = list_sensors()
    readings = latest_sensor_readings()
    sensor_cards = []
    for sensor in sensors:
        temp_c = readings.get(sensor["id"])
        display = format_temp(temp_c, sensor["unit"]) if temp_c is not None else "--"
        sensor_cards.append(
            {
                **sensor,
                "display": display,
            }
        )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "fans": fans,
            "sensors": sensor_cards,
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
                   rotation_seconds, tag, created_at, title_template,
                   value_template, title_font_family, value_font_family,
                   title_font_size, value_font_size
            FROM screens
            ORDER BY created_at DESC
            """
        ).fetchall()
        chain_rows = conn.execute(
            """
            SELECT oc.oled_channel, oc.screen_id, oc.position,
                   s.name, s.rotation_seconds
            FROM oled_chains oc
            JOIN screens s ON s.id = oc.screen_id
            ORDER BY oc.oled_channel, oc.position
            """
        ).fetchall()
    oled_channels = list_oled_channels()
    chains: dict[int, list[dict]] = {}
    chain_ids: dict[int, list[int]] = {oled["channel"]: [] for oled in oled_channels}
    for row in chain_rows:
        channel = row["oled_channel"]
        item = {
            "id": row["screen_id"],
            "name": row["name"],
            "rotation_seconds": row["rotation_seconds"],
        }
        chains.setdefault(channel, []).append(item)
        chain_ids.setdefault(channel, []).append(row["screen_id"])
    return templates.TemplateResponse(
        "screens.html",
        {
            "request": request,
            "screens": [dict(row) for row in rows],
            "fonts": list_font_choices(),
            "oled_channels": oled_channels,
            "tokens": list_token_definitions(),
            "chains": chains,
            "chain_ids": chain_ids,
        },
    )


def _normalize_screen_ids(raw_ids: str | None) -> list[int]:
    if not raw_ids:
        return []
    parsed: list[int] = []
    seen: set[int] = set()
    for item in raw_ids.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError:
            continue
        if value in seen:
            continue
        seen.add(value)
        parsed.append(value)
    return parsed


def _save_oled_chain(conn, oled_channel: int, screen_ids: list[int]) -> list[int]:
    if not screen_ids:
        valid_ids: list[int] = []
    else:
        placeholders = ", ".join("?" for _ in screen_ids)
        rows = conn.execute(
            f"SELECT id FROM screens WHERE id IN ({placeholders})",
            screen_ids,
        ).fetchall()
        valid_set = {row["id"] for row in rows}
        valid_ids = [screen_id for screen_id in screen_ids if screen_id in valid_set]
    conn.execute("DELETE FROM oled_chains WHERE oled_channel = ?", (oled_channel,))
    for position, screen_id in enumerate(valid_ids, start=1):
        conn.execute(
            """
            INSERT INTO oled_chains (oled_channel, screen_id, position)
            VALUES (?, ?, ?)
            """,
            (oled_channel, screen_id, position),
        )
    return valid_ids


def _load_oled_chain(conn, oled_channel: int) -> list[PlaylistScreen]:
    rows = conn.execute(
        """
        SELECT s.name, s.title_template, s.value_template, s.message_template,
               s.font_family, s.font_size, s.title_font_family, s.value_font_family,
               s.title_font_size, s.value_font_size, s.rotation_seconds
        FROM oled_chains oc
        JOIN screens s ON s.id = oc.screen_id
        WHERE oc.oled_channel = ?
        ORDER BY oc.position
        """,
        (oled_channel,),
    ).fetchall()
    screens: list[PlaylistScreen] = []
    for row in rows:
        screens.append(
            PlaylistScreen(
                title_template=row["title_template"] or row["name"] or "",
                value_template=row["value_template"] or row["message_template"] or "",
                title_font=row["title_font_family"] or row["font_family"] or "DejaVu Sans Mono",
                value_font=row["value_font_family"] or row["font_family"] or "DejaVu Sans Mono",
                title_size=int(row["title_font_size"] or 16),
                value_size=int(row["value_font_size"] or row["font_size"] or 22),
                rotation_seconds=int(row["rotation_seconds"] or 15),
            )
        )
    return screens


@app.post("/screens")
def create_screen(
    name: str = Form(...),
    title_template: str = Form(...),
    value_template: str = Form(...),
    title_font_family: str = Form("DejaVu Sans Mono"),
    value_font_family: str = Form("DejaVu Sans Mono"),
    title_font_size: int = Form(16),
    value_font_size: int = Form(22),
    rotation_seconds: int = Form(15),
    tag: str = Form(""),
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO screens (name, message_template, font_family, font_size,
                                 rotation_seconds, tag, title_template, value_template,
                                 title_font_family, value_font_family, title_font_size, value_font_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                value_template,
                value_font_family,
                value_font_size,
                rotation_seconds,
                tag or None,
                title_template,
                value_template,
                title_font_family,
                value_font_family,
                title_font_size,
                value_font_size,
            ),
        )
        conn.commit()
    return RedirectResponse("/screens", status_code=303)


@app.post("/screens/publish")
def publish_oled_chain(
    oled_channel: int = Form(...),
    pixel_shift: str = Form("on"),
    screen_ids: str = Form(""),
):
    with get_connection() as conn:
        normalized = _normalize_screen_ids(screen_ids)
        if screen_ids is not None:
            _save_oled_chain(conn, oled_channel, normalized)
            conn.commit()
        screens = _load_oled_chain(conn, oled_channel)
    if not screens:
        stop_oled_job(int(oled_channel))
        return RedirectResponse("/screens", status_code=303)
    start_oled_job(
        int(oled_channel),
        screens,
        pixel_shift == "on",
    )
    return RedirectResponse("/screens", status_code=303)


@app.post("/screens/chains/update")
def update_oled_chain(
    oled_channel: int = Form(...),
    screen_ids: str = Form(""),
):
    with get_connection() as conn:
        normalized = _normalize_screen_ids(screen_ids)
        _save_oled_chain(conn, oled_channel, normalized)
        conn.commit()
    return RedirectResponse("/screens", status_code=303)


@app.post("/screens/update")
def update_screen(
    screen_id: int = Form(...),
    name: str = Form(...),
    title_template: str = Form(...),
    value_template: str = Form(...),
    title_font_family: str = Form(...),
    value_font_family: str = Form(...),
    title_font_size: int = Form(...),
    value_font_size: int = Form(...),
    rotation_seconds: int = Form(...),
    tag: str = Form(""),
):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE screens
            SET name = ?, title_template = ?, value_template = ?,
                title_font_family = ?, value_font_family = ?,
                title_font_size = ?, value_font_size = ?,
                rotation_seconds = ?, tag = ?, message_template = ?,
                font_family = ?, font_size = ?
            WHERE id = ?
            """,
            (
                name,
                title_template,
                value_template,
                title_font_family,
                value_font_family,
                title_font_size,
                value_font_size,
                rotation_seconds,
                tag or None,
                value_template,
                value_font_family,
                value_font_size,
                screen_id,
            ),
        )
        conn.commit()
    return RedirectResponse("/screens", status_code=303)


@app.post("/screens/delete")
def delete_screen(screen_id: int = Form(...)):
    with get_connection() as conn:
        conn.execute("DELETE FROM screens WHERE id = ?", (screen_id,))
        conn.execute("DELETE FROM oled_chains WHERE screen_id = ?", (screen_id,))
        conn.commit()
    return RedirectResponse("/screens", status_code=303)


@app.post("/screens/off")
def turn_off_oled(oled_channel: int = Form(...)):
    stop_oled_job(int(oled_channel))
    return RedirectResponse("/screens", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    branch, commit_date = get_git_status()
    status = get_status_payload()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "branch": branch,
            "commit_date": commit_date,
            "status": status,
        },
    )


@app.get("/api/admin/status")
def admin_status():
    return JSONResponse(get_status_payload())


@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    fans = list_fans()
    fan_count = get_fan_count()
    sensors = list_sensors()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "fans": fans,
            "fan_count": fan_count,
            "sensors": sensors,
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


@app.post("/settings/sensors")
def update_sensor(sensor_id: int = Form(...), name: str = Form(...), unit: str = Form(...)):
    update_sensor_settings(sensor_id, name, unit)
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/fans/calibrate")
def calibrate_fans(request: Request):
    if _is_calibration_running():
        return _calibration_response(request)
    thread = threading.Thread(target=_run_calibration, daemon=True)
    thread.start()
    return _calibration_response(request)


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


@app.get("/api/temperature/recent")
def get_recent_temperatures(limit: int = 24):
    metrics_rows = recent_metrics(limit=limit)
    cpu = [row["cpu_temp"] for row in metrics_rows]
    ambient = [row["ambient_temp"] for row in metrics_rows]
    sensor_series = recent_sensor_readings(limit=limit)
    sensors = list_sensors()
    sensor_map = {sensor["id"]: sensor for sensor in sensors}
    series = {
        "cpu": cpu,
        "ambient": ambient,
    }
    for sensor_id, values in sensor_series.items():
        series[f"sensor_{sensor_id}"] = values
    labels = [row.get("created_at", "") for row in metrics_rows]
    return JSONResponse(
        {
            "series": series,
            "labels": labels,
            "sensors": [
                {"id": sensor["id"], "name": sensor["name"]}
                for sensor in sensors
                if sensor["id"] in sensor_map
            ],
        }
    )

@app.get("/api/sensors/latest")
def get_latest_sensors():
    sensors = list_sensors()
    readings = latest_sensor_readings()
    payload = []
    for sensor in sensors:
        temp_c = readings.get(sensor["id"])
        payload.append(
            {
                "id": sensor["id"],
                "name": sensor["name"],
                "unit": sensor["unit"],
                "value": format_temp(temp_c, sensor["unit"]) if temp_c is not None else None,
            }
        )
    return JSONResponse({"sensors": payload})


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


@app.get("/api/fans/latest")
def get_latest_fan_rpms():
    return JSONResponse({"fans": latest_fan_readings()})


@app.get("/api/calibration/status")
def get_calibration_status():
    return JSONResponse(_calibration_status_payload())


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


def _run_calibration() -> None:
    logger = get_logger()
    fans = list_fans(active_only=True)
    with _calibration_lock:
        _calibration_state.update(
            {
                "running": True,
                "phase": "calibrating",
                "started_at": time.time(),
                "restore_started_at": 0.0,
                "completed_at": 0.0,
            }
        )
    for fan in fans:
        set_fan_speed(fan["channel_index"], 100)
    time.sleep(_CALIBRATION_SECONDS)
    rpms = get_fan_rpms()
    if not rpms:
        logger.error("no fan rpms found during calibration")
    for channel_index, rpm in rpms.items():
        _update_fan_max_rpm(channel_index, rpm)
    with _calibration_lock:
        _calibration_state["phase"] = "restoring"
        _calibration_state["restore_started_at"] = time.time()
    _restore_after_calibration(fans)
    with _calibration_lock:
        _calibration_state.update(
            {
                "running": False,
                "phase": "complete",
                "completed_at": time.time(),
            }
        )
    logger.info("fan calibration completed")


def _calibration_status_payload() -> dict:
    with _calibration_lock:
        state = dict(_calibration_state)
    if not state["running"]:
        return {"running": False, "phase": "idle", "remaining_seconds": 0}
    now = time.time()
    total_duration = _CALIBRATION_SECONDS + _RESTORE_GRACE_SECONDS
    remaining = max(0, int(total_duration - (now - state["started_at"])))
    return {
        "running": True,
        "phase": state["phase"],
        "remaining_seconds": remaining,
    }


def _is_calibration_running() -> bool:
    with _calibration_lock:
        return bool(_calibration_state["running"])


def _calibration_response(request: Request):
    if "application/json" in request.headers.get("accept", "") or request.headers.get(
        "x-requested-with"
    ):
        return JSONResponse(_calibration_status_payload())
    return RedirectResponse("/settings", status_code=303)


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
