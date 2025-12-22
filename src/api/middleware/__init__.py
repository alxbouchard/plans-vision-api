"""API middleware for authentication, rate limiting, and observability."""

from .auth import APIKeyAuthMiddleware, register_tenant, get_tenant_by_api_key
from .rate_limit import RateLimitMiddleware
from .quotas import check_project_quota, check_page_quota, increment_usage, QuotaExceededError
from .idempotency import IdempotencyMiddleware, get_idempotency_cache
from .request_context import RequestContextMiddleware, metrics

__all__ = [
    "APIKeyAuthMiddleware",
    "RateLimitMiddleware",
    "IdempotencyMiddleware",
    "RequestContextMiddleware",
    "register_tenant",
    "get_tenant_by_api_key",
    "check_project_quota",
    "check_page_quota",
    "increment_usage",
    "QuotaExceededError",
    "get_idempotency_cache",
    "metrics",
]
