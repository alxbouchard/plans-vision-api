"""Structured logging configuration."""

import sys
from datetime import datetime
from typing import Any

import structlog

from src.config import get_settings


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


def configure_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Define processors for structured logging
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Add appropriate renderer based on environment
    if settings.log_level == "DEBUG":
        # Pretty console output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, settings.log_level.upper(), structlog.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class AnalyticsLogger:
    """Logger for analytics events as specified in the spec."""

    def __init__(self):
        self.logger = get_logger("analytics")

    def project_created(self, project_id: str, owner_id: str) -> None:
        """Log project creation event."""
        self.logger.info(
            "project_created",
            project_id=project_id,
            owner_id=owner_id,
            timestamp=datetime.utcnow().isoformat(),
        )

    def page_uploaded(
        self,
        project_id: str,
        page_id: str,
        order: int,
    ) -> None:
        """Log page upload event."""
        self.logger.info(
            "page_uploaded",
            project_id=project_id,
            page_id=page_id,
            order=order,
            timestamp=datetime.utcnow().isoformat(),
        )

    def guide_build_started(self, project_id: str) -> None:
        """Log guide build start event."""
        self.logger.info(
            "guide_build_started",
            project_id=project_id,
            timestamp=datetime.utcnow().isoformat(),
        )

    def guide_build_completed(
        self,
        project_id: str,
        has_stable_guide: bool,
        pages_processed: int,
    ) -> None:
        """Log guide build completion event."""
        self.logger.info(
            "guide_build_completed",
            project_id=project_id,
            has_stable_guide=has_stable_guide,
            pages_processed=pages_processed,
            timestamp=datetime.utcnow().isoformat(),
        )

    def guide_build_failed(
        self,
        project_id: str,
        error_code: str,
        error_message: str,
    ) -> None:
        """Log guide build failure event."""
        self.logger.error(
            "guide_build_failed",
            project_id=project_id,
            error_code=error_code,
            error_message=error_message,
            timestamp=datetime.utcnow().isoformat(),
        )


# Global analytics logger instance
analytics = AnalyticsLogger()
