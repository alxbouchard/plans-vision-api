"""API endpoint tests."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_png


class TestProjects:
    """Tests for project endpoints."""

    @pytest.mark.asyncio
    async def test_create_project(self, client: AsyncClient, headers: dict):
        """Test creating a new project."""
        response = await client.post("/projects", headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "draft"
        assert data["page_count"] == 0

    @pytest.mark.asyncio
    async def test_create_project_missing_owner_id(self, client: AsyncClient):
        """Test creating project without owner ID fails."""
        response = await client.post("/projects")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_project(self, client: AsyncClient, headers: dict):
        """Test getting a project by ID."""
        # Create project first
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        # Get project
        response = await client.get(f"/projects/{project_id}", headers=headers)

        assert response.status_code == 200
        assert response.json()["id"] == project_id

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: AsyncClient, headers: dict):
        """Test getting non-existent project returns 404."""
        response = await client.get(
            "/projects/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, client: AsyncClient, owner_id: str):
        """Test that users cannot access other tenants' projects."""
        # Create project with one owner
        headers1 = {"X-Owner-Id": owner_id}
        create_response = await client.post("/projects", headers=headers1)
        project_id = create_response.json()["id"]

        # Try to access with different owner
        headers2 = {"X-Owner-Id": "11111111-1111-1111-1111-111111111111"}
        response = await client.get(f"/projects/{project_id}", headers=headers2)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_projects(self, client: AsyncClient, headers: dict):
        """Test listing projects."""
        # Create multiple projects
        await client.post("/projects", headers=headers)
        await client.post("/projects", headers=headers)

        response = await client.get("/projects", headers=headers)

        assert response.status_code == 200
        assert len(response.json()) == 2


class TestPages:
    """Tests for page upload endpoints."""

    @pytest.mark.asyncio
    async def test_upload_page(self, client: AsyncClient, headers: dict):
        """Test uploading a page."""
        # Create project
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        # Upload page
        png_data = create_test_png()
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files={"file": ("page1.png", png_data, "image/png")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["order"] == 1
        assert data["project_id"] == project_id

    @pytest.mark.asyncio
    async def test_upload_page_order_increments(self, client: AsyncClient, headers: dict):
        """Test that page order increments correctly."""
        # Create project
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        # Upload multiple pages
        png_data = create_test_png()
        for i in range(3):
            response = await client.post(
                f"/projects/{project_id}/pages",
                headers=headers,
                files={"file": (f"page{i+1}.png", png_data, "image/png")},
            )
            assert response.json()["order"] == i + 1

    @pytest.mark.asyncio
    async def test_upload_non_png_fails(self, client: AsyncClient, headers: dict):
        """Test that non-PNG uploads are rejected."""
        # Create project
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        # Try to upload JPEG
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files={"file": ("page1.jpg", b"fake jpeg data", "image/jpeg")},
        )

        assert response.status_code == 415

    @pytest.mark.asyncio
    async def test_list_pages(self, client: AsyncClient, headers: dict):
        """Test listing pages in a project."""
        # Create project and upload pages
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        png_data = create_test_png()
        await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files={"file": ("page1.png", png_data, "image/png")},
        )
        await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files={"file": ("page2.png", png_data, "image/png")},
        )

        response = await client.get(f"/projects/{project_id}/pages", headers=headers)

        assert response.status_code == 200
        pages = response.json()
        assert len(pages) == 2
        assert pages[0]["order"] == 1
        assert pages[1]["order"] == 2


class TestAnalysis:
    """Tests for analysis endpoints."""

    @pytest.mark.asyncio
    async def test_start_analysis_insufficient_pages(
        self, client: AsyncClient, headers: dict
    ):
        """Test that analysis requires at least 2 pages."""
        # Create project with only 1 page
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        png_data = create_test_png()
        await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files={"file": ("page1.png", png_data, "image/png")},
        )

        # Try to start analysis
        response = await client.post(
            f"/projects/{project_id}/analyze",
            headers=headers,
        )

        assert response.status_code == 422
        assert "2 pages required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_status(self, client: AsyncClient, headers: dict):
        """Test getting analysis status."""
        # Create project
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        response = await client.get(
            f"/projects/{project_id}/status",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "draft"

    @pytest.mark.asyncio
    async def test_get_guide_not_found(self, client: AsyncClient, headers: dict):
        """Test getting guide before analysis returns 404."""
        # Create project
        create_response = await client.post("/projects", headers=headers)
        project_id = create_response.json()["id"]

        response = await client.get(
            f"/projects/{project_id}/guide",
            headers=headers,
        )

        assert response.status_code == 404


class TestHealth:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
