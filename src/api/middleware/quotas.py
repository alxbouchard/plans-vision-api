"""Quota enforcement for multi-tenant resource limits."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, Request, status

from src.config import get_settings
from src.logging import get_logger
from src.models.schemas import SCHEMA_VERSION

logger = get_logger(__name__)


class QuotaExceededError(HTTPException):
    """Exception raised when a quota is exceeded."""

    def __init__(self, quota_type: str, limit: int, message: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "schema_version": SCHEMA_VERSION,
                "error_code": "QUOTA_EXCEEDED",
                "message": message,
                "details": {
                    "quota_type": quota_type,
                    "limit": limit,
                },
            },
        )


def check_project_quota(request: Request) -> None:
    """
    Check if tenant can create more projects.

    Raises QuotaExceededError if limit is reached.
    """
    settings = get_settings()
    tenant = getattr(request.state, "tenant", None)

    if tenant is None:
        # Backwards compatibility mode - no quota enforcement
        return

    if tenant["projects_count"] >= settings.max_projects_per_tenant:
        logger.warning(
            "quota_exceeded",
            tenant_id=str(tenant["tenant_id"]),
            quota_type="projects",
            current=tenant["projects_count"],
            limit=settings.max_projects_per_tenant,
        )
        raise QuotaExceededError(
            quota_type="max_projects_per_tenant",
            limit=settings.max_projects_per_tenant,
            message=f"Maximum projects limit ({settings.max_projects_per_tenant}) reached",
        )


def check_page_quota(request: Request, project_page_count: int) -> None:
    """
    Check if project can accept more pages.

    Args:
        request: The current request
        project_page_count: Current number of pages in the project

    Raises QuotaExceededError if limit is reached.
    """
    settings = get_settings()

    # Check per-project limit
    if project_page_count >= settings.max_pages_per_project:
        logger.warning(
            "quota_exceeded",
            quota_type="pages_per_project",
            current=project_page_count,
            limit=settings.max_pages_per_project,
        )
        raise QuotaExceededError(
            quota_type="max_pages_per_project",
            limit=settings.max_pages_per_project,
            message=f"Maximum pages per project limit ({settings.max_pages_per_project}) reached",
        )

    # Check monthly limit (only if tenant tracking is active)
    tenant = getattr(request.state, "tenant", None)

    if tenant is not None:
        # Check if we need to reset the monthly counter
        usage_reset_at = tenant.get("usage_reset_at")
        if usage_reset_at:
            now = datetime.utcnow()
            # Simple monthly reset: if reset_at is in previous month, we should reset
            if now.month != usage_reset_at.month or now.year != usage_reset_at.year:
                tenant["pages_this_month"] = 0
                tenant["usage_reset_at"] = now

        if tenant["pages_this_month"] >= settings.max_pages_per_month:
            logger.warning(
                "quota_exceeded",
                tenant_id=str(tenant["tenant_id"]),
                quota_type="pages_per_month",
                current=tenant["pages_this_month"],
                limit=settings.max_pages_per_month,
            )
            raise QuotaExceededError(
                quota_type="max_pages_per_month",
                limit=settings.max_pages_per_month,
                message=f"Monthly page limit ({settings.max_pages_per_month}) reached",
            )


def increment_usage(request: Request, projects_delta: int = 0, pages_delta: int = 0) -> None:
    """
    Increment tenant usage counters.

    Call this after successfully creating projects or uploading pages.
    """
    tenant = getattr(request.state, "tenant", None)

    if tenant is not None:
        tenant["projects_count"] += projects_delta
        tenant["pages_this_month"] += pages_delta
        logger.debug(
            "usage_incremented",
            tenant_id=str(tenant["tenant_id"]),
            projects_delta=projects_delta,
            pages_delta=pages_delta,
        )
