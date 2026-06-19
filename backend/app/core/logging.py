"""
Structured logging configuration for ClinicOS Voice.

Uses structlog for JSON logging in production and plain key=value in development.
Import `get_logger()` everywhere — never use print() for observability.

Windows note: run the server with PYTHONUTF8=1 to avoid CP1252 encoding errors.
  e.g.  $env:PYTHONUTF8="1"; uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """
    Configure structlog globally. Call once at application startup (in main.py lifespan).
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.DEBUG or settings.ENVIRONMENT == "development":
        # Use plain key=value renderer to avoid colorama Unicode issues on Windows
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=False),
        ]
        log_level = logging.DEBUG
    else:
        # Machine-readable JSON for production log pipelines
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
        log_level = logging.INFO

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,  # False so stdout wrapper takes effect
    )

    # Quiet down noisy libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.DEBUG else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def get_logger(name: str = "clinicos_voice") -> structlog.BoundLogger:
    """
    Return a named structlog logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("slot_booked", slot_id=str(slot.id))
    """
    return structlog.get_logger(name)
