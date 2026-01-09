# Logging Strategy

This project keeps a simple, auditable logging flow while the platform is still evolving.

## Build logs

- Store build or compose run outputs in `logs/builds/`.
- Use a monotonic suffix, e.g. `docker-compose-build-001.log`.
- Capture the command, result, and raw output for future debugging.

## Runtime logs

- Container logs stay in Docker for now (use `docker compose logs -f` or `docker logs hydrox`).
- If we need retention later, we can add a mounted `logs/runtime/` directory and wire file logging.

## App logging

- FastAPI/uvicorn logs are emitted to stdout/stderr.
- Future plan: add structured JSON logging for metrics ingestion, profile updates, and screen updates.

## When to log

- Failed builds, migrations, and startup errors.
- Major configuration changes (e.g., fan count changes or sensor backends).
