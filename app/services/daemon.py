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
    read_nvme_temp_sensors,
)
from app.services.sensors import (
    insert_sensor_reading,
    read_ds18b20_temps,
    refresh_liquid_sensors,
    sync_ds18b20_sensors,
)
from app.services.profile_control import run_profile_loop
from app.services.settings import get_fan_pwm, get_pump_channel
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
    threading.Thread(target=_sensor_sampler, daemon=True).start()
    threading.Thread(target=run_profile_loop, daemon=True).start()


def _cpu_sampler() -> None:
    while True:
        cpu_temp = read_cpu_temp_vcgencmd()
        if cpu_temp is not None:
            latest = latest_metrics() or {}
            nvme_temp = read_nvme_temp_sensors()
            ambient_temp = nvme_temp if nvme_temp is not None else latest.get(
                "ambient_temp", DEFAULT_METRICS["ambient_temp"]
            )
            fan_rpm = latest.get("fan_rpm", DEFAULT_METRICS["fan_rpm"])
            pump_channel = get_pump_channel()
            pump_percent = None
            if pump_channel is not None:
                pump_percent = get_fan_pwm(pump_channel)
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


def _sensor_sampler() -> None:
    loops = 0
    while True:
        if loops % 12 == 0:
            sync_ds18b20_sensors()
        liquid = refresh_liquid_sensors()
        ds18b20 = read_ds18b20_temps()
        _store_sensor_readings("liquidctl", liquid)
        _store_sensor_readings("ds18b20", ds18b20)
        loops += 1
        time.sleep(5)


def _store_sensor_readings(kind: str, readings: dict[str, float]) -> None:
    if not readings:
        return
    sensor_map = _sensor_id_map(kind)
    for source_id, value in readings.items():
        sensor_id = sensor_map.get(source_id)
        if sensor_id is None:
            continue
        insert_sensor_reading(sensor_id, value)


def _sensor_id_map(kind: str) -> dict[str, int]:
    from app.services.sensors import list_sensors

    sensors = list_sensors()
    return {sensor["source_id"]: sensor["id"] for sensor in sensors if sensor["kind"] == kind}
