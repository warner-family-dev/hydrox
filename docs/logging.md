# Logging Strategy

This project keeps a simple, auditable logging flow while the platform is still evolving.

## Build logs

- Store build output in `logs/builds/docker-compose-buildlog.log`.
- Run `scripts/docker-build-log.py` to append a timestamped record of `docker compose up -d --build`.
- Each line is prepended with a local timestamp (TZ defaults to `America/Chicago`).

## Runtime logs

- Container logs stay in Docker for now (use `docker compose logs -f` or `docker logs hydrox`).
- If we need retention later, we can add a mounted `logs/runtime/` directory and wire file logging.
- App runtime errors are also written to `/logs/hydrox.log` inside the container with local TZ timestamps.

## App logging

- FastAPI/uvicorn logs are emitted to stdout/stderr.
- Liquidctl permission issues and hardware errors are written to `/logs/hydrox.log`.
- Future plan: add structured JSON logging for metrics ingestion, profile updates, and screen updates.

## When to log

- Failed builds, migrations, and startup errors.
- Major configuration changes (e.g., fan count changes or sensor backends).
