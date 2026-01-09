import json
import threading
import time

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_connection, init_db
from app.services.fans import list_fans, seed_fans_if_empty, sync_fan_count, update_fan_name
from app.services.git_info import get_git_status
from app.services.metrics import (
    DEFAULT_METRICS,
    insert_metrics,
    latest_metrics,
    read_cpu_temp_vcgencmd,
    recent_metrics,
    seed_metrics_if_empty,
)
from app.services.settings import get_fan_count, seed_settings_if_empty, set_fan_count

app = FastAPI(title="Hydrox Command Center")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_settings_if_empty()
    seed_metrics_if_empty()
    seed_fans_if_empty()
    thread = threading.Thread(target=_cpu_sampler, daemon=True)
    thread.start()


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


def _build_sparkline_points(values: list[float], width: int = 140, height: int = 40) -> str:
    if not values:
        return ""
    min_val = min(values)
    max_val = max(values)
    span = max(max_val - min_val, 0.01)
    points = []
    for index, value in enumerate(values):
        x = (index / (len(values) - 1)) * width if len(values) > 1 else width / 2
        normalized = (value - min_val) / span
        y = height - (normalized * height)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


@app.get("/", response_class=HTMLResponse)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    metrics = latest_metrics()
    history = recent_metrics()
    cpu_points = _build_sparkline_points([row["cpu_temp"] for row in history])
    ambient_points = _build_sparkline_points([row["ambient_temp"] for row in history])
    fan_points = _build_sparkline_points([row["fan_rpm"] for row in history])
    pump_points = _build_sparkline_points([row["pump_percent"] for row in history])
    fans = list_fans(active_only=True)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "cpu_points": cpu_points,
            "ambient_points": ambient_points,
            "fan_points": fan_points,
            "pump_points": pump_points,
            "fans": fans,
        },
    )


@app.get("/profiles", response_class=HTMLResponse)
def profiles(request: Request):
    rows = _load_profiles()
    return templates.TemplateResponse(
        "profiles.html",
        {
            "request": request,
            "profiles": [dict(row) for row in rows],
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
        return templates.TemplateResponse(
            "profiles.html",
            {
                "request": request,
                "profiles": [dict(row) for row in rows],
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
def rename_fan(fan_id: int = Form(...), name: str = Form(...)):
    update_fan_name(fan_id, name)
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/fan-count")
def update_fan_count(fan_count: int = Form(...)):
    set_fan_count(fan_count)
    sync_fan_count(get_fan_count())
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
