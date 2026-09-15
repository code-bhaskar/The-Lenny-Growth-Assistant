from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger.json import JsonFormatter


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    )
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def info(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.info(message, extra=fields)


def warning(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.warning(message, extra=fields)


def error(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.error(message, extra=fields)
