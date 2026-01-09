# Hydrox Command Center

Hydrox is a Raspberry Pi 5 command center for a wine cellar. It provides a web dashboard for live telemetry, fan/pump profile design, and OLED screen messaging. The stack is a single-container FastAPI app with SQLite storage.

## Features

- Dashboard for CPU temp, ambient temp, fan RPM, and pump output with toggleable trend lines
- Profile Creator for staged fan/pump curves and schedules
- Screen Updater for three OLED panels with templates, font settings, and rotation timing
- Settings page for renaming fan channels and setting the active fan count
- Admin page showing git branch and last commit date

## Stack

- FastAPI + Jinja templates
- SQLite for configuration and metric snapshots
- Docker + docker-compose (single container)

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Docker

```bash
docker compose up --build
```

The service listens on `http://localhost:8000`.

## Compose notes

- The compose file omits the legacy `version` key (Compose v2+ ignores it).
- The container runs as a non-root user and writes SQLite data to `/data`.
- Compose now uses a named volume for `/data` to avoid host permission issues.

## Configuration

- `HYDROX_DB_PATH`: SQLite database path (default: `/data/hydrox.db`)
- `HYDROX_GIT_DIR`: Path to the repo `.git` directory for Admin metadata

## Notes

- Liquidctl integration is staged and will be wired in as host-accessible commands.
- Profiles are created first, then applied manually or via schedules.
- Fan curves are stored per fan channel in the profile JSON and validated on save.

## Logging

- Build logs are stored in `logs/builds/`.
- Runtime logs are kept in Docker for now (use `docker compose logs -f`).
- See `docs/logging.md` for the full plan.
