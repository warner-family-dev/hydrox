import threading
import time

from app.services.cpu_fan import read_cpu_fan_rpm
from app.services.fan_metrics import insert_cpu_fan_reading, insert_fan_reading
from app.services.liquidctl import get_fan_rpms
from app.services.logger import get_logger
from app.services.metrics import (
    DEFAULT_METRICS,
    insert_metrics,
    latest_metrics,
    read_cpu_temp_vcgencmd,
)
from app.services.system_status import _read_wifi_strength, set_wifi_cache

_daemon_started = False
_cpu_fan_missing_logged = False


def start_daemon() -> None:
    global _daemon_started
    if _daemon_started:
        return
    _daemon_started = True
    threading.Thread(target=_cpu_sampler, daemon=True).start()
    threading.Thread(target=_fan_sampler, daemon=True).start()
    threading.Thread(target=_wifi_sampler, daemon=True).start()


def _cpu_sampler() -> None:
    while True:
        cpu_temp = read_cpu_temp_vcgencmd()
        if cpu_temp is not None:
            latest = latest_metrics() or {}
            ambient_temp = latest.get("ambient_temp", DEFAULT_METRICS["ambient_temp"])
            fan_rpm = latest.get("fan_rpm", DEFAULT_METRICS["fan_rpm"])
            pump_percent = latest.get("pump_percent", DEFAULT_METRICS["pump_percent"])
            insert_metrics(cpu_temp, ambient_temp, fan_rpm, pump_percent)
        time.sleep(5)


def _fan_sampler() -> None:
    logger = get_logger()
    global _cpu_fan_missing_logged
    while True:
        rpms = get_fan_rpms()
        for channel_index, rpm in rpms.items():
            insert_fan_reading(channel_index, rpm)
        cpu_rpm = read_cpu_fan_rpm()
        if cpu_rpm is not None:
            insert_cpu_fan_reading(cpu_rpm)
            _cpu_fan_missing_logged = False
        else:
            if not _cpu_fan_missing_logged:
                logger.error("cpu fan rpm not found in sysfs")
                _cpu_fan_missing_logged = True
        time.sleep(5)


def _wifi_sampler() -> None:
    while True:
        set_wifi_cache(_read_wifi_strength())
        time.sleep(5)
