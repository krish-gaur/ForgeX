"""Structured logging with secret masking (architecture §10 — no secrets in logs)."""
from __future__ import annotations

import logging
import re
import sys

import structlog

_SECRET_KEYS = {"password", "password_hash", "token", "access_token", "refresh_token", "authorization", "secret", "secret_key", "api_key", "private_key", "cookie"}
_SECRET_RE = re.compile(r"(bearer\s+)[A-Za-z0-9\-_\.=]+", re.I)


def _mask(_, __, event_dict):
    for k in list(event_dict.keys()):
        if k.lower() in _SECRET_KEYS:
            event_dict[k] = "***"
        elif isinstance(event_dict[k], str) and "bearer" in event_dict[k].lower():
            event_dict[k] = _SECRET_RE.sub(r"\1***", event_dict[k])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, level=getattr(logging, level.upper(), logging.INFO), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _mask,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name) if name else structlog.get_logger()
