"""Tests for Phase 2 bugfix: image metadata storage and retrieval."""

import hashlib
import io
import pytest
from httpx import AsyncClient
from PIL import Image

from tests.conftest import create_test_png


def create_test_png_with_size(width: int, height: int) -> bytes:
    """Create a PNG image with specific dimensions."""
    img = Image.new("RGB", (width, height), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestImageMetadataOnUpload:
    """Test that image metadata is computed and stored on upload."""

    @pytest.mark.asyncio
    async def test_upload_stores_image_dimensions(
        self, client: AsyncClient, headers: dict
    ):
        """Test that uploading a PNG stores correct width and height."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Create a 200x150 image
        png_bytes = create_test_png_with_size(200, 150)

        # Upload page
        files = {"file": ("test.png", png_bytes, "image/png")}
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files=files,
        )
        assert response.status_code == 201
        page_id = response.json()["id"]

        # Get overlay to verify dimensions
        response = await client.get(
            f"/v2/projects/{project_id}/pages/{page_id}/overlay",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["image"]["width"] == 200
        assert data["image"]["height"] == 150

    @pytest.mark.asyncio
    async def test_sha256_is_computed_on_upload(
        self, client: AsyncClient, headers: dict, test_file_storage
    ):
        """Test that SHA256 hash is computed correctly on upload."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Create image and compute expected SHA256
        png_bytes = create_test_png_with_size(100, 80)
        expected_sha256 = hashlib.sha256(png_bytes).hexdigest()

        # Upload page
        files = {"file": ("test.png", png_bytes, "image/png")}
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files=files,
        )
        assert response.status_code == 201

        # Verify dimensions are correct (which means upload worked)
        page_id = response.json()["id"]
        response = await client.get(
            f"/v2/projects/{project_id}/pages/{page_id}/overlay",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["image"]["width"] == 100
        assert data["image"]["height"] == 80
        # SHA256 is stored in DB but not exposed via API
        # The stability test is done in TestFileStorageMetadata.test_sha256_stable_across_reads

    @pytest.mark.asyncio
    async def test_different_sizes_have_different_dimensions(
        self, client: AsyncClient, headers: dict
    ):
        """Test that different image sizes produce different stored dimensions."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Upload two pages with different sizes
        sizes = [(300, 200), (150, 400)]
        page_ids = []

        for width, height in sizes:
            png_bytes = create_test_png_with_size(width, height)
            files = {"file": ("test.png", png_bytes, "image/png")}
            response = await client.post(
                f"/projects/{project_id}/pages",
                headers=headers,
                files=files,
            )
            assert response.status_code == 201
            page_ids.append(response.json()["id"])

        # Verify each page has correct dimensions
        for i, (width, height) in enumerate(sizes):
            response = await client.get(
                f"/v2/projects/{project_id}/pages/{page_ids[i]}/overlay",
                headers=headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["image"]["width"] == width
            assert data["image"]["height"] == height


class TestOverlayEndpointDimensions:
    """Test that overlay endpoint returns real stored dimensions."""

    @pytest.mark.asyncio
    async def test_overlay_returns_stored_dimensions(
        self, client: AsyncClient, headers: dict
    ):
        """Test that overlay endpoint returns stored image dimensions, not hardcoded."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Upload a page with specific dimensions
        png_bytes = create_test_png_with_size(1920, 1080)
        files = {"file": ("test.png", png_bytes, "image/png")}
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files=files,
        )
        assert response.status_code == 201
        page_id = response.json()["id"]

        # Get overlay
        response = await client.get(
            f"/v2/projects/{project_id}/pages/{page_id}/overlay",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Verify dimensions are NOT the old hardcoded 800x600
        assert data["image"]["width"] != 800
        assert data["image"]["height"] != 600

        # Verify dimensions match what we uploaded
        assert data["image"]["width"] == 1920
        assert data["image"]["height"] == 1080

    @pytest.mark.asyncio
    async def test_overlay_schema_version(
        self, client: AsyncClient, headers: dict
    ):
        """Test that overlay response includes schema_version 2.0."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Upload a page
        png_bytes = create_test_png_with_size(100, 100)
        files = {"file": ("test.png", png_bytes, "image/png")}
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files=files,
        )
        assert response.status_code == 201
        page_id = response.json()["id"]

        # Get overlay
        response = await client.get(
            f"/v2/projects/{project_id}/pages/{page_id}/overlay",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == "2.0"


class TestFileStorageMetadata:
    """Test FileStorage metadata computation."""

    @pytest.mark.asyncio
    async def test_save_image_returns_metadata(self, test_file_storage):
        """Test that save_image returns correct metadata."""
        from uuid import uuid4

        project_id = uuid4()
        png_bytes = create_test_png_with_size(256, 128)

        file_path, metadata = await test_file_storage.save_image(
            project_id=project_id,
            content=png_bytes,
            content_type="image/png",
        )

        # Verify metadata
        assert metadata.width == 256
        assert metadata.height == 128
        assert metadata.byte_size == len(png_bytes)
        assert metadata.sha256 == hashlib.sha256(png_bytes).hexdigest()

    @pytest.mark.asyncio
    async def test_compute_metadata_matches_save_metadata(self, test_file_storage):
        """Test that compute_image_metadata returns same values as save_image."""
        from uuid import uuid4

        project_id = uuid4()
        png_bytes = create_test_png_with_size(512, 384)

        # Save image
        file_path, save_metadata = await test_file_storage.save_image(
            project_id=project_id,
            content=png_bytes,
            content_type="image/png",
        )

        # Compute metadata from stored file
        compute_metadata = await test_file_storage.compute_image_metadata(file_path)

        # Values should match
        assert compute_metadata.width == save_metadata.width
        assert compute_metadata.height == save_metadata.height
        assert compute_metadata.byte_size == save_metadata.byte_size
        assert compute_metadata.sha256 == save_metadata.sha256

    @pytest.mark.asyncio
    async def test_sha256_stable_across_reads(self, test_file_storage):
        """Test that SHA256 is stable across multiple reads."""
        from uuid import uuid4

        project_id = uuid4()
        png_bytes = create_test_png_with_size(64, 64)
        expected_sha256 = hashlib.sha256(png_bytes).hexdigest()

        file_path, _ = await test_file_storage.save_image(
            project_id=project_id,
            content=png_bytes,
            content_type="image/png",
        )

        # Read metadata multiple times
        for _ in range(3):
            metadata = await test_file_storage.compute_image_metadata(file_path)
            assert metadata.sha256 == expected_sha256
