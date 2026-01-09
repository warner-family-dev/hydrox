import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LOG_PATH_ENV = "HYDROX_LOG_PATH"
DEFAULT_LOG_PATH = "/logs/hydrox.log"
DEFAULT_TZ = "America/Chicago"


_logger = None


class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        tz_name = os.getenv("TZ", DEFAULT_TZ)
        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = ZoneInfo(DEFAULT_TZ)
        dt = datetime.fromtimestamp(record.created, tz=tzinfo)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def now_local() -> str:
    tz_name = os.getenv("TZ", DEFAULT_TZ)
    try:
        tzinfo = ZoneInfo(tz_name)
    except Exception:
        tzinfo = ZoneInfo(DEFAULT_TZ)
    return datetime.now(tzinfo).strftime("%Y-%m-%d %H:%M:%S")


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    log_path = os.getenv(LOG_PATH_ENV, DEFAULT_LOG_PATH)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hydrox")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = LocalTimeFormatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _logger = logger
    return logger
