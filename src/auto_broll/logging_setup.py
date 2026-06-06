from __future__ import annotations

import logging


LOGGER_NAME = "auto_broll"


def setup_logging(level: str = "INFO") -> logging.Logger:
    normalized = (level or "INFO").upper()
    numeric_level = getattr(logging, normalized, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unknown log level: {level}")

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(numeric_level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)

    for handler in logger.handlers:
        handler.setLevel(numeric_level)

    return logger
