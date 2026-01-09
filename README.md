# Hydrox Command Center

Hydrox is a Raspberry Pi 5 command center for a wine cellar. It provides a web dashboard for live telemetry, fan/pump profile design, and OLED screen messaging. The stack is a single-container FastAPI app with SQLite storage.

## Features

- Dashboard for CPU temp, ambient temp, fan RPM, and pump output
- Profile Creator for staged fan/pump curves and schedules
- Screen Updater for three OLED panels with templates, font settings, and rotation timing
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
docker-compose up --build
```

The service listens on `http://localhost:8000`.

## Configuration

- `HYDROX_DB_PATH`: SQLite database path (default: `/data/hydrox.db`)
- `HYDROX_GIT_DIR`: Path to the repo `.git` directory for Admin metadata

## Notes

- Liquidctl integration is staged and will be wired in as host-accessible commands.
- Profiles are created first, then applied manually or via schedules.
