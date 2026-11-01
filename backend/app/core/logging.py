"""Structured JSON logging with request IDs and PII masking."""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TextIO

from app.core.config import Settings
from app.core.masking import SENSITIVE_FIELDS, mask_text

request_id_context: ContextVar[str] = ContextVar("request_id", default="")

# Attributes set by the logging module itself; anything else on the record is
# treated as an extra field supplied by the caller.
RESERVED_RECORD_ATTRIBUTES = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class PIIMaskingFilter(logging.Filter):
    """Mask emails, phone numbers, and sensitive fields on every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_text(record.msg)

        if isinstance(record.args, dict):
            record.args = {key: _mask_value(key, value) for key, value in record.args.items()}
        elif isinstance(record.args, tuple):
            record.args = tuple(_mask_value(None, value) for value in record.args)

        for key, value in list(record.__dict__.items()):
            if key in RESERVED_RECORD_ATTRIBUTES:
                continue
            record.__dict__[key] = _mask_value(key, value)

        return True


def _mask_value(key: str | None, value: object) -> object:
    if key in SENSITIVE_FIELDS:
        return "[REDACTED]" if value else value
    if isinstance(value, str):
        return mask_text(value)
    return value


class JSONFormatter(logging.Formatter):
    """Render each record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_text(record.getMessage()),
        }

        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key in RESERVED_RECORD_ATTRIBUTES or key.startswith("_"):
                continue
            if key in SENSITIVE_FIELDS:
                payload[key] = "[REDACTED]" if value else value
            elif isinstance(value, str):
                payload[key] = mask_text(value)
            else:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(settings: Settings, stream: TextIO | None = None) -> None:
    """Install the JSON handler and masking filter on the root logger."""
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(PIIMaskingFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # Route uvicorn through the root handler so its output is structured and
    # masked too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        for existing in list(logger.handlers):
            logger.removeHandler(existing)
        logger.propagate = True


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)
