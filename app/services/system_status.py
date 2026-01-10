import os
import shutil
import subprocess
import time
from pathlib import Path

from app.services.liquidctl import has_liquidctl_devices
from app.services.logger import get_logger


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
_WIFI_CACHE: dict | None = None


def set_image_start_time(epoch_seconds: float) -> None:
    global _IMAGE_START
    _IMAGE_START = epoch_seconds


def get_image_uptime() -> str:
    if _IMAGE_START is None:
        return "unknown"
    elapsed = max(0, int(time.time() - _IMAGE_START))
    return _format_duration(elapsed)


def set_wifi_cache(payload: dict) -> None:
    global _WIFI_CACHE
    _WIFI_CACHE = payload


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
    if _WIFI_CACHE is not None:
        return _WIFI_CACHE
    return _read_wifi_strength(interface)


def _read_wifi_strength(interface: str = "wlan0") -> dict:
    logger = get_logger()
    desired = os.getenv("HYDROX_WIFI_INTERFACE", interface)
    iw_result = _read_iw_signal(desired)
    if iw_result is not None:
        return iw_result
    wpa_result = _read_wpa_signal(desired)
    if wpa_result is not None:
        return wpa_result
    proc_path = os.getenv("HYDROX_WIFI_PROC_PATH", "/proc/net/wireless")
    sysfs_result = _read_sysfs_wifi(desired)
    if sysfs_result is not None:
        return sysfs_result
    try:
        lines = _read_proc(proc_path).splitlines()[2:]
    except OSError:
        _log_wifi_once(
            "_wifi_proc_missing_logged",
            "wifi strength unavailable: %s not readable",
            proc_path,
        )
        return {"label": "unknown", "percent": None, "interface": desired}
    entries: dict[str, float] = {}
    for line in lines:
        if not line.strip():
            continue
        name, data = line.split(":", 1)
        parts = data.split()
        if len(parts) < 2:
            _log_wifi_once(
                "_wifi_parse_logged",
                "wifi strength parse error: missing link value for %s",
                name.strip(),
            )
            continue
        try:
            link = float(parts[1])
        except ValueError:
            _log_wifi_once(
                "_wifi_parse_logged",
                "wifi strength parse error: non-numeric link value for %s",
                name.strip(),
            )
            continue
        entries[name.strip()] = link
    if not entries:
        _log_wifi_once("_wifi_parse_logged", "wifi strength unavailable: no wireless interfaces found")
        return {"label": "unknown", "percent": None, "interface": desired}
    if desired not in entries:
        fallback = next(iter(entries.keys()))
        _log_wifi_once(
            "_wifi_missing_logged",
            "wifi strength unavailable: interface %s not found; using %s",
            desired,
            fallback,
        )
        desired = fallback
    percent = int(max(0, min(100, round(entries[desired] / 70 * 100))))
    return {"label": _wifi_label(percent), "percent": percent, "interface": desired}


def _wifi_label(percent: int) -> str:
    if percent < 25:
        return "Poor"
    if percent < 50:
        return "OK"
    if percent < 75:
        return "Good"
    return "Excellent"


_wifi_proc_missing_logged = False
_wifi_parse_logged = False
_wifi_missing_logged = False
_wifi_sys_missing_logged = False
_wifi_wpa_missing_logged = False
_wifi_iw_missing_logged = False


def _log_wifi_once(flag_name: str, message: str, *args: object) -> None:
    global _wifi_proc_missing_logged, _wifi_parse_logged, _wifi_missing_logged, _wifi_sys_missing_logged
    global _wifi_wpa_missing_logged, _wifi_iw_missing_logged
    flags = {
        "_wifi_proc_missing_logged": _wifi_proc_missing_logged,
        "_wifi_parse_logged": _wifi_parse_logged,
        "_wifi_missing_logged": _wifi_missing_logged,
        "_wifi_sys_missing_logged": _wifi_sys_missing_logged,
        "_wifi_wpa_missing_logged": _wifi_wpa_missing_logged,
        "_wifi_iw_missing_logged": _wifi_iw_missing_logged,
    }
    if flags.get(flag_name):
        return
    get_logger().error(message, *args)
    if flag_name == "_wifi_proc_missing_logged":
        _wifi_proc_missing_logged = True
    elif flag_name == "_wifi_parse_logged":
        _wifi_parse_logged = True
    elif flag_name == "_wifi_missing_logged":
        _wifi_missing_logged = True
    elif flag_name == "_wifi_sys_missing_logged":
        _wifi_sys_missing_logged = True
    elif flag_name == "_wifi_wpa_missing_logged":
        _wifi_wpa_missing_logged = True
    elif flag_name == "_wifi_iw_missing_logged":
        _wifi_iw_missing_logged = True


def _read_sysfs_wifi(interface: str) -> dict | None:
    base_path = os.getenv("HYDROX_WIFI_SYS_PATH", "/host-sys/class/net")
    link_path = Path(base_path) / interface / "wireless" / "link"
    if not link_path.exists():
        _log_wifi_once(
            "_wifi_sys_missing_logged",
            "wifi strength unavailable: %s not found",
            link_path,
        )
        return None
    try:
        link_raw = link_path.read_text(encoding="utf-8").strip()
        link_value = float(link_raw)
    except OSError:
        _log_wifi_once(
            "_wifi_sys_missing_logged",
            "wifi strength unavailable: %s not readable",
            link_path,
        )
        return None
    except ValueError:
        _log_wifi_once(
            "_wifi_parse_logged",
            "wifi strength parse error: non-numeric link value for %s",
            interface,
        )
        return None
    percent = int(max(0, min(100, round(link_value / 70 * 100))))
    return {"label": _wifi_label(percent), "percent": percent, "interface": interface}


def _read_wpa_signal(interface: str) -> dict | None:
    socket_path = os.getenv("HYDROX_WIFI_WPA_PATH", "/host-run/wpa_supplicant")
    try:
        result = subprocess.run(
            ["wpa_cli", "-p", socket_path, "-i", interface, "signal_poll"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        _log_wifi_once("_wifi_wpa_missing_logged", "wifi strength unavailable: wpa_cli not installed")
        return None
    if result.returncode != 0:
        _log_wifi_once(
            "_wifi_wpa_missing_logged",
            "wifi strength unavailable: wpa_cli failed for %s: %s",
            interface,
            result.stderr.strip() or result.stdout.strip(),
        )
        return None
    rssi = _parse_wpa_signal(result.stdout)
    if rssi is None:
        _log_wifi_once(
            "_wifi_parse_logged",
            "wifi strength parse error: wpa_cli missing RSSI for %s",
            interface,
        )
        return None
    percent = _signal_to_percent(rssi)
    return {"label": _wifi_label(percent), "percent": percent, "interface": interface}


def _read_iw_signal(interface: str) -> dict | None:
    try:
        result = subprocess.run(
            ["iw", "dev", interface, "link"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        _log_wifi_once("_wifi_iw_missing_logged", "wifi strength unavailable: iw not installed")
        return None
    if result.returncode != 0:
        _log_wifi_once(
            "_wifi_iw_missing_logged",
            "wifi strength unavailable: iw failed for %s: %s",
            interface,
            result.stderr.strip() or result.stdout.strip(),
        )
        return None
    if "Not connected." in result.stdout:
        return {"label": "unknown", "percent": None, "interface": interface}
    signal = _parse_iw_signal(result.stdout)
    if signal is None:
        _log_wifi_once(
            "_wifi_parse_logged",
            "wifi strength parse error: iw missing signal for %s",
            interface,
        )
        return None
    percent = _signal_to_percent(signal)
    return {"label": _wifi_label(percent), "percent": percent, "interface": interface}


def _parse_wpa_signal(output: str) -> int | None:
    for line in output.splitlines():
        if line.startswith("RSSI="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def _parse_iw_signal(output: str) -> int | None:
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("signal:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(float(parts[1]))
                except ValueError:
                    return None
    return None


def _signal_to_percent(signal_dbm: int) -> int:
    normalized = 2 * (signal_dbm + 100)
    return int(max(0, min(100, normalized)))


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
