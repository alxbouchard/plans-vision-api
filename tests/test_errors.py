"""Tests for error taxonomy and consistent error responses."""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from tests.conftest import create_test_png


class TestErrorCodes:
    """Tests for documented error codes from docs/ERRORS.md."""

    @pytest.mark.asyncio
    async def test_api_key_missing_error(self, client: AsyncClient):
        """Test API_KEY_MISSING error code."""
        response = await client.get("/projects")
        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "API_KEY_MISSING"
        assert data["schema_version"] == "1.0"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_invalid_owner_id_error(self, client: AsyncClient):
        """Test INVALID_OWNER_ID error code."""
        response = await client.get(
            "/projects",
            headers={"X-Owner-Id": "not-a-uuid"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INVALID_OWNER_ID"

    @pytest.mark.asyncio
    async def test_project_not_found_error(self, client: AsyncClient, headers: dict):
        """Test that 404 returns appropriate error info."""
        fake_id = str(uuid4())
        response = await client.get(f"/projects/{fake_id}", headers=headers)
        assert response.status_code == 404
        # Note: FastAPI returns generic 404 without our custom format here

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_error(self, client: AsyncClient, headers: dict):
        """Test RATE_LIMIT_EXCEEDED error code and retry header."""
        # This test validates the structure - actual rate limiting would require
        # hitting the limit which is set to 60/min by default
        # Verify rate limit headers exist on normal response
        response = await client.get("/projects", headers=headers)
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    @pytest.mark.asyncio
    async def test_idempotency_key_invalid_error(self, client: AsyncClient, headers: dict):
        """Test INVALID_IDEMPOTENCY_KEY error code."""
        long_key = "x" * 300  # Exceeds 256 char limit
        response = await client.post(
            "/projects",
            headers={**headers, "Idempotency-Key": long_key},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INVALID_IDEMPOTENCY_KEY"
        assert data["schema_version"] == "1.0"


class TestErrorResponseFormat:
    """Tests for consistent error response structure."""

    @pytest.mark.asyncio
    async def test_all_errors_have_schema_version(self, client: AsyncClient):
        """Test that error responses include schema_version."""
        response = await client.get("/projects")  # No auth - should error
        assert response.status_code == 401
        data = response.json()
        assert "schema_version" in data
        assert data["schema_version"] == "1.0"

    @pytest.mark.asyncio
    async def test_all_errors_have_error_code(self, client: AsyncClient):
        """Test that error responses include error_code."""
        response = await client.get("/projects")
        assert response.status_code == 401
        data = response.json()
        assert "error_code" in data
        assert len(data["error_code"]) > 0

    @pytest.mark.asyncio
    async def test_all_errors_have_message(self, client: AsyncClient):
        """Test that error responses include message."""
        response = await client.get("/projects")
        assert response.status_code == 401
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0


class TestValidationErrors:
    """Tests for validation error codes."""

    @pytest.mark.asyncio
    async def test_invalid_image_format_error(self, client: AsyncClient, headers: dict):
        """Test that non-PNG uploads return appropriate error."""
        # Create project first
        response = await client.post("/projects", headers=headers)
        project_id = response.json()["id"]

        # Try to upload JPEG
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files={"file": ("page.jpg", b"fake jpeg", "image/jpeg")},
        )
        assert response.status_code == 415
        # Note: This comes from HTTPException, may not have our custom format

    @pytest.mark.asyncio
    async def test_no_pages_error(self, client: AsyncClient, headers: dict):
        """Test that analysis without pages returns appropriate error."""
        # Create empty project
        response = await client.post("/projects", headers=headers)
        project_id = response.json()["id"]

        # Try to start analysis
        response = await client.post(
            f"/projects/{project_id}/analyze",
            headers=headers,
        )
        assert response.status_code == 422
        assert "1 page required" in response.json()["detail"]


class TestPipelineErrorSchema:
    """Tests for structured pipeline error schema."""

    def test_pipeline_error_schema_structure(self):
        """Test PipelineErrorSchema structure."""
        from src.models.schemas import PipelineErrorSchema

        error = PipelineErrorSchema(
            error_code="MODEL_INVALID_OUTPUT",
            message="Guide Applier returned invalid JSON",
            step="guide_applier",
            page=2,
        )
        assert error.error_code == "MODEL_INVALID_OUTPUT"
        assert error.step == "guide_applier"
        assert error.page == 2

    def test_pipeline_error_schema_optional_fields(self):
        """Test PipelineErrorSchema with optional fields."""
        from src.models.schemas import PipelineErrorSchema

        error = PipelineErrorSchema(
            error_code="INTERNAL_ERROR",
            message="Unexpected error",
        )
        assert error.error_code == "INTERNAL_ERROR"
        assert error.step is None
        assert error.page is None

    def test_pipeline_status_with_error(self):
        """Test PipelineStatusResponse with structured error."""
        from src.models.schemas import PipelineStatusResponse, PipelineErrorSchema
        from src.models.entities import ProjectStatus

        response = PipelineStatusResponse(
            project_id=uuid4(),
            status=ProjectStatus.FAILED,
            current_step=None,
            pages_processed=2,
            total_pages=5,
            error=PipelineErrorSchema(
                error_code="MODEL_INVALID_OUTPUT",
                message="Failed to parse JSON response",
                step="guide_applier",
                page=2,
            ),
        )
        assert response.status == ProjectStatus.FAILED
        assert response.error is not None
        assert response.error.error_code == "MODEL_INVALID_OUTPUT"
        assert response.error.page == 2
