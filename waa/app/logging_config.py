"""Logger setup with rotation and secret redaction."""
from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from app.config import settings


class SecretRedactor(logging.Formatter):
    """Formatter that redacts API keys, tokens, and passwords."""

    _PATTERNS = [
        (re.compile(r"(apikey|api[_-]?key|token|password|secret|auth)[\s:=]+\S+", re.I), "****"),
        (re.compile(r"sk-[A-Za-z0-9]{10,}"), "sk-****"),
        (re.compile(r"(Bearer\s+)[A-Za-z0-9._-]+"), r"\1****"),
    ]

    def format(self, record: logging.LogRecord) -> str:
        result = super().format(record)
        for pattern, replacement in self._PATTERNS:
            result = pattern.sub(replacement, result)
        return result


def setup_logging() -> logging.Logger:
    data_dir = settings.logs_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    log_file = data_dir / f"waa_{datetime.now().strftime('%Y%m%d')}.log"
    formatter = SecretRedactor(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        TimedRotatingFileHandler(
            log_file,
            when="midnight",
            backupCount=getattr(settings, "log_retention_days", 30),
            encoding="utf-8",
        ),
    ]

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )
    return logging.getLogger("waa")


logger = setup_logging()
