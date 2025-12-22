"""Rate limiting middleware using fixed window algorithm."""

from __future__ import annotations

import time
from typing import Callable, Dict
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config import get_settings
from src.logging import get_logger
from src.models.schemas import SCHEMA_VERSION

logger = get_logger(__name__)


class RateLimitWindow:
    """Fixed window rate limit tracker."""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.window_duration = 60  # seconds
        # tenant_id -> (window_start_time, request_count)
        self._windows: Dict[UUID, tuple[float, int]] = {}

    def is_allowed(self, tenant_id: UUID) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.

        Returns:
            (is_allowed, remaining_requests, reset_in_seconds)
        """
        current_time = time.time()
        window_data = self._windows.get(tenant_id)

        if window_data is None:
            # First request from this tenant
            self._windows[tenant_id] = (current_time, 1)
            return (True, self.requests_per_minute - 1, self.window_duration)

        window_start, request_count = window_data

        # Check if window has expired
        if current_time - window_start >= self.window_duration:
            # Start new window
            self._windows[tenant_id] = (current_time, 1)
            return (True, self.requests_per_minute - 1, self.window_duration)

        # Within current window
        remaining_time = int(self.window_duration - (current_time - window_start))

        if request_count >= self.requests_per_minute:
            # Rate limit exceeded
            return (False, 0, remaining_time)

        # Allow request and increment counter
        self._windows[tenant_id] = (window_start, request_count + 1)
        remaining = self.requests_per_minute - request_count - 1
        return (True, remaining, remaining_time)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting API requests.

    Uses a fixed window algorithm per tenant.
    Requires APIKeyAuthMiddleware to run first (sets request.state.tenant_id).
    """

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app, requests_per_minute: int | None = None):
        super().__init__(app)
        settings = get_settings()
        self.rate_limiter = RateLimitWindow(
            requests_per_minute or settings.rate_limit_requests_per_minute
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get tenant_id from auth middleware
        tenant_id = getattr(request.state, "tenant_id", None)

        if tenant_id is None:
            # Auth middleware should have handled this, but be safe
            return await call_next(request)

        # Check rate limit
        is_allowed, remaining, reset_in = self.rate_limiter.is_allowed(tenant_id)

        if not is_allowed:
            logger.warning(
                "rate_limit_exceeded",
                tenant_id=str(tenant_id),
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "schema_version": SCHEMA_VERSION,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please retry later.",
                    "details": {"retry_after_seconds": reset_in},
                },
                headers={
                    "Retry-After": str(reset_in),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_in),
                },
            )

        # Process request and add rate limit headers to response
        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(
            self.rate_limiter.requests_per_minute
        )
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)

        return response
