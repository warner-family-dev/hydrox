from dataclasses import dataclass

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


@dataclass
class ScreenPayload:
    message: str
    font_key: str
    font_size: int


def list_font_choices() -> list[dict]:
    return [{"key": key, "label": key} for key in FONT_CHOICES.keys()]


def list_oled_channels() -> list[dict]:
    return [{"label": label, "channel": channel} for label, channel in OLED_CHANNELS.items()]


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


def _select_channel(channel: int) -> None:
    mask = 1 << channel
    with SMBus(I2C_BUS) as bus:
        bus.write_byte(PCA_ADDR, mask)


def _load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_CHOICES.get(key) or FONT_CHOICES["DejaVu Sans Mono"]
    return ImageFont.truetype(path, size)
