import shutil
import time
from pathlib import Path

from app.services.liquidctl import has_liquidctl_devices


def _read_proc(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def get_uptime() -> str:
    try:
        raw = _read_proc("/proc/uptime").split()[0]
        total_seconds = int(float(raw))
    except (OSError, ValueError, IndexError):
        return "unknown"
    return _format_duration(total_seconds)


_IMAGE_START: float | None = None


def set_image_start_time(epoch_seconds: float) -> None:
    global _IMAGE_START
    _IMAGE_START = epoch_seconds


def get_image_uptime() -> str:
    if _IMAGE_START is None:
        return "unknown"
    elapsed = max(0, int(time.time() - _IMAGE_START))
    return _format_duration(elapsed)


def get_memory_usage() -> str:
    try:
        data = _read_proc("/proc/meminfo").splitlines()
        mem_total = _meminfo_value(data, "MemTotal")
        mem_available = _meminfo_value(data, "MemAvailable")
        if mem_total is None or mem_available is None:
            return "unknown"
        used_kb = max(mem_total - mem_available, 0)
        total_mb = mem_total / 1024
        used_mb = used_kb / 1024
        percent = (used_kb / mem_total * 100) if mem_total else 0.0
        return f"{used_mb:.0f} / {total_mb:.0f} MB ({percent:.1f}%)"
    except OSError:
        return "unknown"


def _meminfo_value(lines: list[str], key: str) -> int | None:
    for line in lines:
        if line.startswith(key):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    return None
    return None


def get_liquidctl_status() -> str:
    try:
        return "Connected" if has_liquidctl_devices() else "Not connected"
    except Exception:
        return "unknown"


def get_cpu_usage() -> str:
    try:
        total_1, idle_1 = _read_cpu_times()
        time.sleep(0.1)
        total_2, idle_2 = _read_cpu_times()
    except OSError:
        return "unknown"
    delta_total = total_2 - total_1
    delta_idle = idle_2 - idle_1
    if delta_total <= 0:
        return "unknown"
    busy = max(delta_total - delta_idle, 0)
    percent = busy / delta_total * 100
    return f"{percent:.1f}%"


def _read_cpu_times() -> tuple[int, int]:
    line = _read_proc("/proc/stat").splitlines()[0]
    parts = line.split()
    if not parts or parts[0] != "cpu":
        raise OSError("cpu stats unavailable")
    values = [int(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return total, idle


def get_disk_usage(path: str) -> str:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return "unknown"
    used = usage.used
    total = usage.total
    percent = (used / total * 100) if total else 0.0
    return f"{_format_gb(used)} / {_format_gb(total)} GB ({percent:.1f}%)"


def _format_gb(value: int) -> str:
    gb = value / (1024**3)
    return f"{gb:.2f}"


def _format_duration(total_seconds: int) -> str:
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_wifi_strength(interface: str = "wlan0") -> dict:
    try:
        lines = _read_proc("/proc/net/wireless").splitlines()[2:]
    except OSError:
        return {"label": "unknown", "percent": None}
    for line in lines:
        if not line.strip():
            continue
        name, data = line.split(":", 1)
        if name.strip() != interface:
            continue
        parts = data.split()
        if len(parts) < 2:
            break
        try:
            link = float(parts[1])
        except ValueError:
            break
        percent = int(max(0, min(100, round(link / 70 * 100))))
        return {"label": _wifi_label(percent), "percent": percent}
    return {"label": "unknown", "percent": None}


def _wifi_label(percent: int) -> str:
    if percent < 25:
        return "Poor"
    if percent < 50:
        return "OK"
    if percent < 75:
        return "Good"
    return "Excellent"


def get_status_payload() -> dict:
    return {
        "status": "Ok",
        "host_uptime": get_uptime(),
        "image_uptime": get_image_uptime(),
        "cpu": get_cpu_usage(),
        "memory": get_memory_usage(),
        "disk_data": get_disk_usage("/data"),
        "liquidctl": get_liquidctl_status(),
        "wifi": get_wifi_strength(),
    }
