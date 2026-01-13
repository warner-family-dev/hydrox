import random
import threading
import time
from dataclasses import dataclass

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

from app.services.fan_metrics import latest_fan_readings, recent_cpu_fan_readings
from app.services.fans import list_fans
from app.services.logger import get_logger
from app.services.metrics import latest_metrics
from app.services.oled import FONT_CHOICES, I2C_BUS, OLED_ADDR, clear_screen, select_oled_channel
from app.services.sensors import format_temp, latest_sensor_readings, list_sensors

_active_jobs: dict[int, "OLEDJob"] = {}
_lock = threading.Lock()
_render_lock = threading.Lock()
_REFRESH_SECONDS = 5


@dataclass(frozen=True)
class PlaylistScreen:
    title_template: str
    value_template: str
    title_font: str
    value_font: str
    title_size: int
    value_size: int
    rotation_seconds: int


class OLEDJob:
    def __init__(
        self,
        channel: int,
        screens: list[PlaylistScreen],
        brightness_percent: int,
        pixel_shift: bool,
        start_time: float | None,
    ) -> None:
        self.channel = channel
        self.screens = screens
        self.brightness_percent = brightness_percent
        self.pixel_shift = pixel_shift
        self.start_time = start_time
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        logger = get_logger()
        if not self.screens:
            clear_screen(self.channel)
            return
        device = None
        font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        shift_x = 0
        shift_y = 0
        next_shift = time.time() + 60
        if self.start_time:
            wait = self.start_time - time.time()
            if wait > 0:
                self._stop_event.wait(wait)
        while not self._stop_event.is_set():
            for screen in self.screens:
                if self._stop_event.is_set():
                    break
                rotation_seconds = max(int(screen.rotation_seconds), 1)
                end_at = time.time() + rotation_seconds
                title_font = _cached_font(font_cache, screen.title_font, screen.title_size)
                value_font = _cached_font(font_cache, screen.value_font, screen.value_size)
                while time.time() < end_at and not self._stop_event.is_set():
                    if device is None:
                        device = self._init_device(logger)
                        if device is None:
                            self._stop_event.wait(2)
                            continue
                    if self.pixel_shift and time.time() >= next_shift:
                        shift_x = random.randint(-2, 2)
                        shift_y = random.randint(-2, 2)
                        next_shift = time.time() + 60
                    elif not self.pixel_shift:
                        shift_x = 0
                        shift_y = 0
                    tokens = build_token_map()
                    title = render_template(screen.title_template, tokens)
                    value = render_template(screen.value_template, tokens)
                    try:
                        with _render_lock:
                            select_oled_channel(self.channel)
                            with canvas(device) as draw:
                                draw.text((0 + shift_x, 0 + shift_y), title, font=title_font, fill=255)
                                draw.text((0 + shift_x, 24 + shift_y), value, font=value_font, fill=255)
                    except Exception:
                        logger.exception("oled render failed for channel %s", self.channel)
                        device = None
                    remaining = end_at - time.time()
                    if remaining <= 0:
                        break
                    self._stop_event.wait(min(_REFRESH_SECONDS, remaining))

    def _init_device(self, logger) -> ssd1306 | None:
        try:
            select_oled_channel(self.channel)
            serial = i2c(port=I2C_BUS, address=OLED_ADDR)
            device = ssd1306(serial, width=128, height=64)
            brightness = int(max(0, min(100, self.brightness_percent)))
            device.contrast(int(brightness / 100 * 255))
            return device
        except Exception:
            logger.exception("oled job failed to initialize for channel %s", self.channel)
            return None


def start_oled_job(
    channel: int,
    screens: list[PlaylistScreen],
    brightness_percent: int,
    pixel_shift: bool,
    start_time: float | None = None,
) -> None:
    with _lock:
        existing = _active_jobs.get(channel)
        if existing:
            existing.stop()
        job = OLEDJob(channel, screens, brightness_percent, pixel_shift, start_time)
        _active_jobs[channel] = job
        job.start()


def stop_oled_job(channel: int) -> None:
    with _lock:
        existing = _active_jobs.pop(channel, None)
    if existing:
        existing.stop()
    clear_screen(channel)


def render_template(template: str, tokens: dict[str, str]) -> str:
    result = template
    for key, value in tokens.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


def build_token_map() -> dict[str, str]:
    tokens: dict[str, str] = {}
    metrics = latest_metrics() or {}
    if "cpu_temp" in metrics and metrics["cpu_temp"] is not None:
        tokens["cpu_temp"] = f"{metrics['cpu_temp']:.1f}°C"
    if "ambient_temp" in metrics and metrics["ambient_temp"] is not None:
        tokens["ambient_temp"] = f"{metrics['ambient_temp']:.1f}°C"
    if "pump_percent" in metrics and metrics["pump_percent"] is not None:
        tokens["pump_percent"] = f"{metrics['pump_percent']}%"

    fans = list_fans()
    fan_readings = {row["channel_index"]: row["rpm"] for row in latest_fan_readings()}
    for fan in fans:
        channel = fan["channel_index"]
        rpm = fan_readings.get(channel)
        if rpm is not None:
            tokens[f"fan{channel}_rpm"] = f"{rpm}"
            if fan.get("max_rpm"):
                percent = min(max(rpm / fan["max_rpm"] * 100, 0), 100)
                tokens[f"fan{channel}_percent"] = f"{percent:.0f}%"
    cpu_fan_rows = recent_cpu_fan_readings(limit=1)
    if cpu_fan_rows:
        tokens["cpu_fan_rpm"] = f"{cpu_fan_rows[0]['rpm']}"
    sensors = list_sensors()
    sensor_readings = latest_sensor_readings()
    for sensor in sensors:
        temp_c = sensor_readings.get(sensor["id"])
        if temp_c is None:
            continue
        tokens[f"sensor_{sensor['id']}"] = format_temp(temp_c, sensor["unit"])
        tokens[sensor["name"].lower().replace(" ", "_")] = format_temp(temp_c, sensor["unit"])
    return tokens


def list_token_definitions() -> list[dict]:
    items = [
        {"label": "CPU Temp", "token": "{{cpu_temp}}"},
        {"label": "NVMe Temp", "token": "{{ambient_temp}}"},
        {"label": "Pump Percent", "token": "{{pump_percent}}"},
    ]
    fans = list_fans()
    for fan in fans:
        channel = fan["channel_index"]
        items.append({"label": f"Fan {channel} PWM (RPM)", "token": f"{{{{fan{channel}_rpm}}}}"})
        items.append({"label": f"Fan {channel} %", "token": f"{{{{fan{channel}_percent}}}}"})
    items.append({"label": "CPU Fan RPM", "token": "{{cpu_fan_rpm}}"})
    sensors = list_sensors()
    for sensor in sensors:
        items.append({"label": sensor["name"], "token": f"{{{{sensor_{sensor['id']}}}}}"})
    return items


def _load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_CHOICES.get(key) or FONT_CHOICES["DejaVu Sans Mono"]
    return ImageFont.truetype(path, size)


def _cached_font(cache: dict[tuple[str, int], ImageFont.FreeTypeFont], key: str, size: int) -> ImageFont.FreeTypeFont:
    cache_key = (key, size)
    if cache_key in cache:
        return cache[cache_key]
    font = _load_font(key, size)
    cache[cache_key] = font
    return font
