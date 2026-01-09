# Hydrox Command Center

Hydrox is a Raspberry Pi 5 command center for a wine cellar. It provides a web dashboard for live telemetry, fan/pump profile design, and OLED screen messaging. The stack is a single-container FastAPI app with SQLite storage.

## Features

- Dashboard for CPU temp, ambient temp, fan RPM, and pump output with toggleable trend lines
- Fan output chart with per-fan calibration and max RPM tracking
- Profile Creator for staged fan/pump curves and schedules
- Screen Updater for three OLED panels with templates, font settings, and rotation timing
- Settings page for renaming fan channels and setting the active fan count
- Admin page showing git branch and last commit date

## Stack

- FastAPI + Jinja templates
- SQLite for configuration and metric snapshots
- Docker + docker-compose (single container, includes git and `vcgencmd` for Admin/CPU metadata)

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

## Build logging

Use the wrapper to capture timestamped build output:

```bash
scripts/docker-build-log.py
```

Build logs append to `logs/builds/docker-compose-buildlog.log`.

## Compose notes

- The compose file omits the legacy `version` key (Compose v2+ ignores it).
- The container runs as a non-root user and writes SQLite data to `/data`.
- Compose now uses a named volume for `/data` to avoid host permission issues.
- App logs are written to `/logs/hydrox.log` (mapped to `./logs` on the host).
- The container runs as root to access hardware while preserving file permissions via `PUID`/`PGID`.
- The container runs in `privileged` mode to access USB devices like the Octo.

## Configuration

- `HYDROX_DB_PATH`: SQLite database path (default: `/data/hydrox.db`)
- `HYDROX_GIT_DIR`: Path to the repo `.git` directory for Admin metadata
- `HYDROX_LIQUIDCTL_PATH`: Optional path override for `liquidctl` (default: `/root/.local/bin/liquidctl`)
- `HYDROX_LOG_PATH`: Path to the app log file (default: `/logs/hydrox.log`)

## Notes

- Liquidctl integration is shipped in the image (builder stage).
- Profiles are created first, then applied manually or via schedules.
- Fan curves are stored per fan channel in the profile JSON and validated on save.
- Admin metadata falls back to `unknown` when git metadata is unavailable in the container.
- Admin commit dates render as `YYYY-MM-DD HH:MM:SS CPT`.
- `.dockerignore` excludes logs, env files, and local dev artifacts.
- `.gitignore` keeps logs, env files, and local dev artifacts out of version control.
- CPU temperature is sampled every 5 seconds via `vcgencmd measure_temp` and stored in SQLite.
- Dashboard metrics auto-refresh every 2 seconds via the metrics API, with a single temperature trend chart.
- Fan output chart uses max RPM values from Settings calibration or manual entry.
- CPU fan RPM reads return 0 when idle; missing sysfs paths log once per boot.
- Calibration shows a countdown modal while the fan sweep runs.

## Logging

- Build logs are stored in `logs/builds/`.
- Build logs include the local datetime of the run.
- Build logs record early failures such as missing packages.
- Runtime logs are kept in Docker for now (use `docker compose logs -f`).
- App runtime errors and permission issues are written to `/logs/hydrox.log` using local TZ timestamps, with a startup banner.
- See `docs/logging.md` for the full plan.

## Raspberry Pi tooling

- The Docker image enables `vcgencmd` by adding the Raspberry Pi apt repo and installing `libraspberrypi-bin`.
- The image keeps build tooling installed so `smbus` can compile during `liquidctl` installation.
- The container needs access to the VideoCore device for `vcgencmd` (`/dev/vcio` on Pi 5).
- If `/dev/vcio` is missing, create it on the host: `sudo mknod /dev/vcio c 100 0` and ensure Docker can access it.
- The image installs `liquidctl` in a builder stage and ships it at `/root/.local/bin/liquidctl`.
- USB devices are passed through via `/dev/bus/usb` for liquidctl device access.
- VideoCore device access is provided via `/dev/vcio`.
