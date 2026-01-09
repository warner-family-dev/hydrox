#!/usr/bin/env python3
import os
import subprocess
import sys
from datetime import datetime

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


def main() -> int:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    cmd = ["docker", "compose", "up", "-d", "--build"]
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
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
    return return_code


if __name__ == "__main__":
    sys.exit(main())
