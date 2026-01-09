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
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_memory_usage() -> str:
    try:
        data = _read_proc("/proc/meminfo").splitlines()
        mem_total = _meminfo_value(data, "MemTotal")
        mem_available = _meminfo_value(data, "MemAvailable")
        if mem_total is None or mem_available is None:
            return "unknown"
        used_kb = max(mem_total - mem_available, 0)
        used_mb = used_kb / 1024
        return f"{used_mb:.2f} MB"
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


def get_status_payload() -> dict:
    return {
        "status": "Ok",
        "uptime": get_uptime(),
        "memory": get_memory_usage(),
        "liquidctl": get_liquidctl_status(),
    }
