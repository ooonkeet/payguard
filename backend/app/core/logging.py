"""Structured logging configuration for PayGuard."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    """Compact structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_record.update(record.extra_data)
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record, default=str)


def setup_logging() -> logging.Logger:
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger("payguard")
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.propagate = False
    return root_logger


logger = setup_logging()

