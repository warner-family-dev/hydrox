import os
import re
import subprocess
from typing import Dict, Tuple

from app.services.logger import get_logger

LIQUIDCTL_PATH_ENV = "HYDROX_LIQUIDCTL_PATH"
DEFAULT_LIQUIDCTL_PATH = "/root/.local/bin/liquidctl"


def _candidate_paths() -> list[str]:
    env_path = os.getenv(LIQUIDCTL_PATH_ENV, DEFAULT_LIQUIDCTL_PATH)
    paths = [env_path, "/root/.local/bin/liquidctl", "/usr/local/bin/liquidctl", "/usr/bin/liquidctl"]
    deduped = []
    for path in paths:
        if path and path not in deduped:
            deduped.append(path)
    return deduped


def _run_liquidctl(args: list[str]) -> Tuple[int, str, str]:
    logger = get_logger()
    last_error = "liquidctl not found"
    for path in _candidate_paths():
        cmd = [path] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            logger.error("liquidctl not found at %s", path)
            last_error = "liquidctl not found"
            continue
        except PermissionError:
            logger.error("liquidctl permission denied at %s", path)
            last_error = "liquidctl permission denied"
            continue
        if result.returncode != 0:
            logger.error("liquidctl command failed: %s | stderr=%s", " ".join(cmd), result.stderr.strip())
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    return 127, "", last_error


def set_fan_speed(channel_index: int, percent: int) -> bool:
    code, _, _ = _run_liquidctl(["set", f"fan{channel_index}", "speed", str(percent)])
    return code == 0


def get_fan_rpms() -> Dict[int, int]:
    logger = get_logger()
    _, stdout, _ = _run_liquidctl(["status"])
    rpms: Dict[int, int] = {}
    for line in stdout.splitlines():
        match = re.search(r"fan\s*(\d+).*?(\d+)\s*rpm", line, re.IGNORECASE)
        if match:
            try:
                channel = int(match.group(1))
                rpm = int(match.group(2))
                rpms[channel] = rpm
            except ValueError:
                continue
    if not rpms:
        logger.error("liquidctl status returned no fan RPMs")
    return rpms


def get_liquid_temps() -> list[float]:
    logger = get_logger()
    _, stdout, _ = _run_liquidctl(["status"])
    temps: list[float] = []
    for line in stdout.splitlines():
        if "temp" not in line.lower():
            continue
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*°?C", line)
        if match:
            try:
                temps.append(float(match.group(1)))
            except ValueError:
                continue
    if not temps:
        logger.error("liquidctl status returned no temperatures")
    return temps


def has_liquidctl_devices() -> bool:
    _, stdout, _ = _run_liquidctl(["list"])
    return "Device #" in stdout
