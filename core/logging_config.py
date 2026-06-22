from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


DEFAULT_LOG_FILE = "hrms_system.log"
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    *,
    log_file: str | Path | None = None,
    level: str | int | None = None,
) -> None:
    """Configure application-wide logging once for CLI and daemon entrypoints."""
    log_level = _resolve_log_level(level or os.getenv("HRMS_LOG_LEVEL", DEFAULT_LOG_LEVEL))
    log_path = Path(log_file or os.getenv("HRMS_LOG_FILE", DEFAULT_LOG_FILE))

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    logging.getLogger(__name__).debug(
        "Logging configured with level=%s file=%s",
        logging.getLevelName(log_level),
        log_path,
    )


def _resolve_log_level(level: str | int) -> int:
    if isinstance(level, int):
        return level

    resolved = logging.getLevelName(level.upper())
    if isinstance(resolved, int):
        return resolved

    return logging.INFO
