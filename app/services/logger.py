import logging
import os
from pathlib import Path

LOG_PATH_ENV = "HYDROX_LOG_PATH"
DEFAULT_LOG_PATH = "/logs/hydrox.log"


_logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    log_path = os.getenv(LOG_PATH_ENV, DEFAULT_LOG_PATH)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hydrox")
    logger.setLevel(logging.INFO)

    handler = logging.FileHandler(log_path)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    _logger = logger
    return logger
