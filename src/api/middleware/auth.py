"""API Key authentication middleware."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config import get_settings
from src.logging import get_logger
from src.models.schemas import SCHEMA_VERSION

logger = get_logger(__name__)


# In-memory tenant store for v1 (Phase 1.5)
# In production, this would be backed by database
_tenant_store: dict[str, dict] = {}


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new API key."""
    return f"pv_{secrets.token_urlsafe(32)}"


def register_tenant(name: str, tenant_id: Optional[UUID] = None) -> tuple[UUID, str]:
    """
    Register a new tenant and return (tenant_id, api_key).

    The api_key should be shown to the user once and never stored in plain text.
    """
    from uuid import uuid4

    tenant_id = tenant_id or uuid4()
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)

    _tenant_store[key_hash] = {
        "tenant_id": tenant_id,
        "name": name,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "projects_count": 0,
        "pages_this_month": 0,
        "usage_reset_at": datetime.utcnow(),
    }

    logger.info("tenant_registered", tenant_id=str(tenant_id), name=name)
    return tenant_id, api_key


def get_tenant_by_api_key(api_key: str) -> Optional[dict]:
    """Look up tenant by API key."""
    key_hash = hash_api_key(api_key)
    return _tenant_store.get(key_hash)


def update_tenant_usage(api_key: str, projects_delta: int = 0, pages_delta: int = 0) -> None:
    """Update tenant usage counters."""
    key_hash = hash_api_key(api_key)
    tenant = _tenant_store.get(key_hash)
    if tenant:
        tenant["projects_count"] += projects_delta
        tenant["pages_this_month"] += pages_delta


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.

    Validates X-API-Key header and injects tenant_id into request state.
    Falls back to X-Owner-Id for backwards compatibility in Phase 1.5.
    """

    # Paths that don't require authentication
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip auth for CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Try X-API-Key first
        api_key = request.headers.get("X-API-Key")

        if api_key:
            tenant = get_tenant_by_api_key(api_key)

            if tenant is None:
                return self._error_response(
                    status_code=401,
                    error_code="API_KEY_INVALID",
                    message="Invalid API key",
                )

            if not tenant["is_active"]:
                return self._error_response(
                    status_code=403,
                    error_code="TENANT_DISABLED",
                    message="Tenant account is disabled",
                )

            # Inject tenant info into request state
            request.state.tenant_id = tenant["tenant_id"]
            request.state.tenant = tenant
            request.state.api_key = api_key

            logger.debug(
                "auth_success",
                tenant_id=str(tenant["tenant_id"]),
                method=request.method,
                path=request.url.path,
            )

        else:
            # Fallback: check X-Owner-Id for backwards compatibility
            owner_id = request.headers.get("X-Owner-Id")

            if not owner_id:
                return self._error_response(
                    status_code=401,
                    error_code="API_KEY_MISSING",
                    message="Missing X-API-Key header",
                )

            # Backwards compatibility: use owner_id as tenant_id
            try:
                request.state.tenant_id = UUID(owner_id)
                request.state.tenant = None  # No tenant record
                request.state.api_key = None
            except ValueError:
                return self._error_response(
                    status_code=400,
                    error_code="INVALID_OWNER_ID",
                    message="Invalid X-Owner-Id: must be a valid UUID",
                )

        return await call_next(request)

    def _error_response(
        self,
        status_code: int,
        error_code: str,
        message: str,
    ) -> JSONResponse:
        """Create a standardized error response with CORS headers."""
        return JSONResponse(
            status_code=status_code,
            content={
                "schema_version": SCHEMA_VERSION,
                "error_code": error_code,
                "message": message,
                "details": None,
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "true",
            },
        )
