"""FastAPI dependencies for dependency injection."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage import get_session, FileStorage


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get a database session."""
    async for session in get_session():
        yield session


def get_file_storage() -> FileStorage:
    """Dependency to get file storage instance."""
    return FileStorage()


def get_tenant_id(request: Request) -> UUID:
    """
    Get tenant ID from auth middleware (X-API-Key).

    This is the primary way to get tenant context.
    The APIKeyAuthMiddleware sets request.state.tenant_id.
    """
    if hasattr(request.state, "tenant_id") and request.state.tenant_id:
        return request.state.tenant_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide X-API-Key header",
    )


# Alias for backwards compatibility
get_owner_id = get_tenant_id
