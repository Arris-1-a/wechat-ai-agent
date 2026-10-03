"""Logger setup."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from app.config import settings


def setup_logging() -> logging.Logger:
    data_dir = settings.logs_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    log_file = data_dir / f"waa_{datetime.now().strftime('%Y%m%d')}.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )

    return logging.getLogger("waa")


logger = setup_logging()
