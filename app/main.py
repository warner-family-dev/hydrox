from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_connection, init_db
from app.services.fans import list_fans, seed_fans_if_empty, update_fan_name
from app.services.git_info import get_git_status
from app.services.metrics import insert_metrics, latest_metrics, recent_metrics, seed_metrics_if_empty

app = FastAPI(title="Hydrox Command Center")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_metrics_if_empty()
    seed_fans_if_empty()


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
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "metrics": metrics,
            "cpu_points": cpu_points,
            "ambient_points": ambient_points,
        },
    )


@app.get("/profiles", response_class=HTMLResponse)
def profiles(request: Request):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, curve_json, schedule_json, created_at
            FROM profiles
            ORDER BY created_at DESC
            """
        ).fetchall()
    return templates.TemplateResponse(
        "profiles.html",
        {
            "request": request,
            "profiles": [dict(row) for row in rows],
        },
    )


@app.post("/profiles")
def create_profile(
    name: str = Form(...),
    curve_json: str = Form(...),
    schedule_json: str = Form(""),
):
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
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "fans": fans,
        },
    )


@app.post("/settings/fans")
def rename_fan(fan_id: int = Form(...), name: str = Form(...)):
    update_fan_name(fan_id, name)
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
