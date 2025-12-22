"""Idempotency key support for safe retries."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, StreamingResponse

from src.logging import get_logger
from src.models.schemas import SCHEMA_VERSION

logger = get_logger(__name__)


# Cache TTL in seconds (24 hours)
IDEMPOTENCY_CACHE_TTL = 86400


class IdempotencyCache:
    """
    In-memory cache for idempotency keys.

    Stores: idempotency_key -> (response_status, response_body, timestamp)
    """

    def __init__(self, ttl: int = IDEMPOTENCY_CACHE_TTL):
        self.ttl = ttl
        # (tenant_id, idempotency_key) -> (status_code, body, created_at)
        self._cache: Dict[tuple[UUID, str], tuple[int, bytes, float]] = {}

    def get(self, tenant_id: UUID, key: str) -> Optional[tuple[int, bytes]]:
        """Get cached response for idempotency key."""
        cache_key = (tenant_id, key)
        entry = self._cache.get(cache_key)

        if entry is None:
            return None

        status_code, body, created_at = entry

        # Check if expired
        if time.time() - created_at > self.ttl:
            del self._cache[cache_key]
            return None

        return (status_code, body)

    def set(
        self,
        tenant_id: UUID,
        key: str,
        status_code: int,
        body: bytes,
    ) -> None:
        """Cache response for idempotency key."""
        cache_key = (tenant_id, key)
        self._cache[cache_key] = (status_code, body, time.time())

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        now = time.time()
        expired_keys = [
            key
            for key, (_, _, created_at) in self._cache.items()
            if now - created_at > self.ttl
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


# Global cache instance
_idempotency_cache = IdempotencyCache()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for idempotency key support.

    Handles Idempotency-Key header for POST/PUT/PATCH requests.
    Re-sent requests with same key return cached response.
    """

    # Methods that support idempotency
    IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}

    # Paths that support idempotency
    IDEMPOTENT_PATHS = {
        "/projects",  # Create project
        "/analyze",   # Start analysis (ends with /analyze)
    }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Only apply to idempotent methods
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        # Check if path supports idempotency
        path = request.url.path
        if not self._is_idempotent_path(path):
            return await call_next(request)

        # Get idempotency key from header
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            # No idempotency key - process normally
            return await call_next(request)

        # Validate key format (should be UUID-like or reasonable string)
        if len(idempotency_key) > 256:
            return JSONResponse(
                status_code=400,
                content={
                    "schema_version": SCHEMA_VERSION,
                    "error_code": "INVALID_IDEMPOTENCY_KEY",
                    "message": "Idempotency key too long (max 256 characters)",
                    "details": None,
                },
            )

        # Get tenant_id from auth middleware
        tenant_id = getattr(request.state, "tenant_id", None)

        if tenant_id is None:
            # Auth middleware should have handled this
            return await call_next(request)

        # Check cache
        cached = _idempotency_cache.get(tenant_id, idempotency_key)

        if cached is not None:
            status_code, body = cached
            logger.info(
                "idempotency_cache_hit",
                tenant_id=str(tenant_id),
                idempotency_key=idempotency_key,
                path=path,
            )
            return Response(
                content=body,
                status_code=status_code,
                media_type="application/json",
                headers={"X-Idempotency-Replayed": "true"},
            )

        # Process request
        response = await call_next(request)

        # Only cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            # Read response body (need to buffer for caching)
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            _idempotency_cache.set(
                tenant_id,
                idempotency_key,
                response.status_code,
                body,
            )

            logger.debug(
                "idempotency_cached",
                tenant_id=str(tenant_id),
                idempotency_key=idempotency_key,
                path=path,
            )

            # Return new response with body
            return Response(
                content=body,
                status_code=response.status_code,
                media_type=response.media_type,
                headers=dict(response.headers),
            )

        return response

    def _is_idempotent_path(self, path: str) -> bool:
        """Check if path supports idempotency."""
        for idempotent_path in self.IDEMPOTENT_PATHS:
            if path == idempotent_path or path.endswith(idempotent_path):
                return True
        # Also support /projects/{id}/pages uploads
        if "/pages" in path:
            return True
        return False


def get_idempotency_cache() -> IdempotencyCache:
    """Get the global idempotency cache instance."""
    return _idempotency_cache
