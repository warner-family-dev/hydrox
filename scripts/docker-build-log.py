#!/usr/bin/env python3
import os
import subprocess
import sys
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

LOG_PATH = os.path.join("logs", "builds", "docker-compose-buildlog.log")
DEFAULT_TZ = "America/Chicago"


def _timestamp() -> str:
    tz_name = os.getenv("TZ", DEFAULT_TZ)
    if ZoneInfo:
        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = ZoneInfo(DEFAULT_TZ)
        return datetime.now(tzinfo).strftime("%Y-%m-%d %H:%M:%S %z")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_line(handle, line: str) -> None:
    handle.write(f"[{_timestamp()}] {line}\n")
    handle.flush()

def _collect_container_logs(handle, since_iso: str) -> None:
    cmd = ["docker", "compose", "logs", "-t", "--no-color", "--since", since_iso, "hydrox"]
    _write_line(handle, f"COMMAND: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stdout:
        for line in result.stdout.splitlines():
            _write_line(handle, line)
    if result.stderr:
        for line in result.stderr.splitlines():
            _write_line(handle, f"LOGS_ERROR: {line}")


def main() -> int:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    cmd = ["docker", "compose", "up", "-d", "--build"]
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        start_time = datetime.now(timezone.utc).isoformat()
        _write_line(handle, f"COMMAND: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            _write_line(handle, line.rstrip())
        return_code = process.wait()
        _write_line(handle, f"EXIT_CODE: {return_code}")
        _collect_container_logs(handle, start_time)
    return return_code


if __name__ == "__main__":
    sys.exit(main())
