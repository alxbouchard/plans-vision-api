"""FastAPI dependencies for dependency injection."""

from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage import get_session, FileStorage


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get a database session."""
    async for session in get_session():
        yield session


def get_file_storage() -> FileStorage:
    """Dependency to get file storage instance."""
    return FileStorage()


async def get_owner_id(
    x_owner_id: str = Header(..., description="Owner/tenant ID for isolation")
) -> UUID:
    """
    Extract and validate owner ID from request header.

    This provides tenant isolation - users can only access their own projects.
    """
    try:
        return UUID(x_owner_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Owner-Id header: must be a valid UUID",
        )
