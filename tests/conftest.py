"""Pytest fixtures for Plans Vision API tests."""

import os
import tempfile
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.api.app import create_app
from src.api.dependencies import get_db_session, get_file_storage
from src.storage.database import Base
from src.storage.file_storage import FileStorage


# Set test environment
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[async_sessionmaker, None]:
    """Create a test database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield session_factory

    await engine.dispose()


@pytest.fixture
def test_upload_dir() -> str:
    """Create a temporary upload directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_file_storage(test_upload_dir: str) -> FileStorage:
    """Create a test file storage instance."""
    return FileStorage(base_dir=test_upload_dir)


@pytest_asyncio.fixture
async def app(
    test_db: async_sessionmaker,
    test_file_storage: FileStorage,
) -> FastAPI:
    """Create test application with overridden dependencies."""
    app = create_app()

    async def override_get_session():
        async with test_db() as session:
            yield session

    def override_get_file_storage():
        return test_file_storage

    app.dependency_overrides[get_db_session] = override_get_session
    app.dependency_overrides[get_file_storage] = override_get_file_storage

    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def owner_id() -> str:
    """Generate a test owner ID."""
    return str(uuid4())


@pytest.fixture
def headers(owner_id: str) -> dict:
    """Default headers including owner ID."""
    return {"X-Owner-Id": owner_id}


def create_test_png() -> bytes:
    """Create a minimal valid PNG image for testing."""
    # Minimal 1x1 white PNG
    import io
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
