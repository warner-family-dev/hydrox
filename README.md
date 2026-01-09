# Hydrox Command Center

Hydrox is a Raspberry Pi 5 command center for a wine cellar. It provides a web UI for live telemetry, fan/pump profile management, OLED screen messaging, and admin status.

## Features

- Dashboard for CPU temperature, ambient temperature, fan RPMs, and pump output
- Profile Creator for per-fan curves and schedules (cron + time windows)
- Screen Updater for three OLED panels with templates, fonts, and rotation timing
- Settings for fan naming, fan count, and calibration/max RPM tracking
- Admin status with git metadata, uptime, CPU load, memory, disk usage, and Wi-Fi strength

## Stack

- FastAPI + Jinja templates
- SQLite for configuration and metrics
- Docker + Docker Compose (single container)

## Requirements

- Raspberry Pi 5
- Docker + Docker Compose
- Access to VideoCore (`/dev/vcio`) for `vcgencmd`
- USB access for liquidctl devices (Octo)

## Quick start (Docker)

```bash
docker compose up --build
```

The service listens on `http://localhost:8000`.

## Configuration

Environment variables (via `docker-compose.yml`):

- `HYDROX_DB_PATH`: SQLite database path (default: `/data/hydrox.db`)
- `HYDROX_GIT_DIR`: Path to the repo `.git` directory for Admin metadata
- `HYDROX_LIQUIDCTL_PATH`: Optional path override for `liquidctl` (default: `/root/.local/bin/liquidctl`)
- `HYDROX_LOG_PATH`: Path to the app log file (default: `/logs/hydrox.log`)
- `TZ`: Local timezone (used for logs)
- `PUID` / `PGID`: File ownership mapping for logs and data

## Logging

- App runtime logs: `logs/hydrox.log`
- Build logs: `logs/builds/docker-compose-buildlog.log`
- Use `scripts/docker-build-log.py` to capture timestamped build output
- Wi-Fi strength reads from `/proc/net/wireless`; missing interfaces are logged to `hydrox.log`
- Admin status values auto-refresh every 5 seconds.

## Hardware notes

- `vcgencmd` is used for CPU temperature sampling.
- `liquidctl` is bundled in the container for fan/pump control and RPM reads.
- The container runs in privileged mode to access USB devices.
- If `/dev/vcio` is missing on the host, create it with:

```bash
sudo mknod /dev/vcio c 100 0
```

## Development (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
