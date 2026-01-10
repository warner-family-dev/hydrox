from dataclasses import dataclass
import os
import shutil

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont
from smbus2 import SMBus

from app.services.logger import get_logger

I2C_BUS = 1
PCA_ADDR = 0x70
OLED_ADDR = 0x3C

OLED_CHANNELS = {
    "OLED 1": 5,
    "OLED 2": 6,
    "OLED 3": 7,
}

FONT_CHOICES = {
    "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVu Sans Mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "Liberation Sans": "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "Liberation Mono": "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
}

FONT_WEB_FILES = {
    "DejaVu Sans": "DejaVuSans.ttf",
    "DejaVu Sans Mono": "DejaVuSansMono.ttf",
    "Liberation Sans": "LiberationSans-Regular.ttf",
    "Liberation Mono": "LiberationMono-Regular.ttf",
}


@dataclass
class ScreenPayload:
    message: str
    font_key: str
    font_size: int


def list_font_choices() -> list[dict]:
    return [{"key": key, "label": key} for key in FONT_CHOICES.keys()]


def list_oled_channels() -> list[dict]:
    return [{"label": label, "channel": channel} for label, channel in OLED_CHANNELS.items()]


def ensure_web_fonts(static_dir: str = "app/static/fonts") -> None:
    logger = get_logger()
    os.makedirs(static_dir, exist_ok=True)
    for name, source in FONT_CHOICES.items():
        filename = FONT_WEB_FILES.get(name)
        if not filename:
            continue
        target = os.path.join(static_dir, filename)
        if os.path.exists(target):
            continue
        try:
            shutil.copyfile(source, target)
        except FileNotFoundError:
            logger.warning("oled font file missing for web preview: %s", source)
        except OSError:
            logger.exception("oled font copy failed for %s", source)


def select_oled_channel(channel: int) -> None:
    _select_channel(channel)


def disable_oled_channel() -> None:
    _disable_channel()


def publish_screen(payload: ScreenPayload, channel: int) -> None:
    logger = get_logger()
    try:
        _select_channel(channel)
        serial = i2c(port=I2C_BUS, address=OLED_ADDR)
        device = ssd1306(serial, width=128, height=64)
        font = _load_font(payload.font_key, payload.font_size)
        with canvas(device) as draw:
            draw.text((0, 0), payload.message, font=font, fill=255)
    except Exception:
        logger.exception("oled publish failed for channel %s", channel)


def clear_screen(channel: int) -> None:
    logger = get_logger()
    try:
        _select_channel(channel)
        serial = i2c(port=I2C_BUS, address=OLED_ADDR)
        device = ssd1306(serial, width=128, height=64)
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline=0, fill=0)
        _disable_channel()
    except Exception:
        logger.exception("oled clear failed for channel %s", channel)


def _select_channel(channel: int) -> None:
    mask = 1 << channel
    with SMBus(I2C_BUS) as bus:
        bus.write_byte(PCA_ADDR, mask)


def _disable_channel() -> None:
    with SMBus(I2C_BUS) as bus:
        bus.write_byte(PCA_ADDR, 0x00)


def _load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_CHOICES.get(key) or FONT_CHOICES["DejaVu Sans Mono"]
    return ImageFont.truetype(path, size)
