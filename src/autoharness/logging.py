"""Structured logging setup with conservative redaction."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|credential)")


def redact_event(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> Mapping[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in event_dict.items():
        if SECRET_PATTERN.search(key) or (isinstance(value, str) and SECRET_PATTERN.search(value)):
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value
    return redacted


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            redact_event,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )
