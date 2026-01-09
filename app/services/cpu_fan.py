from glob import glob
from typing import Optional


def read_cpu_fan_rpm() -> Optional[int]:
    paths = glob("/sys/devices/platform/cooling_fan/hwmon/*/fan1_input")
    if not paths:
        paths = glob("/sys/class/hwmon/hwmon*/fan1_input")
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read().strip()
            value = int(raw)
            return value
        except (OSError, ValueError):
            continue
    return None
