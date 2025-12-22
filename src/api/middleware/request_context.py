"""Request context middleware for observability."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from src.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request context and observability.

    Adds:
    - X-Request-ID header (generated or from client)
    - Request timing and logging
    - Structured logging context (tenant_id, request_id)
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Generate or use provided request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state
        request.state.request_id = request_id

        # Get tenant_id if available (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", None)

        # Bind context vars for structured logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            tenant_id=str(tenant_id) if tenant_id else None,
            path=request.url.path,
            method=request.method,
        )

        # Time the request
        start_time = time.time()

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Add request ID to response
            response.headers["X-Request-ID"] = request_id

            # Log request completion
            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            return response

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=duration_ms,
            )
            raise


class MetricsLogger:
    """
    Logger for metrics tracking.

    Outputs structured log events that can be aggregated by log analysis tools.
    """

    def __init__(self):
        self.logger = get_logger("metrics")

    def record_page_processed(
        self,
        project_id: str,
        tenant_id: str | None,
        duration_ms: int,
        success: bool,
    ) -> None:
        """Record a page processing metric."""
        self.logger.info(
            "metric_pages_processed",
            project_id=project_id,
            tenant_id=tenant_id,
            duration_ms=duration_ms,
            success=success,
            count=1,
        )

    def record_guide_generated(
        self,
        project_id: str,
        tenant_id: str | None,
        is_stable: bool,
        pages_count: int,
        duration_ms: int,
    ) -> None:
        """Record guide generation metric."""
        self.logger.info(
            "metric_guides_generated" if is_stable else "metric_guides_provisional",
            project_id=project_id,
            tenant_id=tenant_id,
            pages_count=pages_count,
            duration_ms=duration_ms,
            count=1,
        )

    def record_guide_rejected(
        self,
        project_id: str,
        tenant_id: str | None,
        reason: str,
    ) -> None:
        """Record guide rejection metric."""
        self.logger.info(
            "metric_guides_rejected",
            project_id=project_id,
            tenant_id=tenant_id,
            reason=reason,
            count=1,
        )

    def record_pipeline_step(
        self,
        project_id: str,
        step: str,
        duration_ms: int,
        outcome: str,
        page: int | None = None,
        error_code: str | None = None,
    ) -> None:
        """Record pipeline step execution metric."""
        self.logger.info(
            "metric_pipeline_step",
            project_id=project_id,
            step=step,
            page=page,
            duration_ms=duration_ms,
            outcome=outcome,
            error_code=error_code,
        )


# Global metrics logger instance
metrics = MetricsLogger()
