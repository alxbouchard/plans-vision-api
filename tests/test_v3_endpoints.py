"""Tests for V3 API endpoints.

Tests the real V3 endpoints per API_CONTRACT_Render_v3.md:
- PDF upload
- Build mapping
- Get mapping status
- Get mapping metadata
- Render PDF
- Get render status
- Render annotations

Key gates:
- Gate 1: Fingerprint mismatch refusal (PDF_MISMATCH)
- Gate 2: Mapping required refusal (MAPPING_REQUIRED)
- Gate 6: Renderer is pure (zero model calls)
"""

import io
import pytest
from uuid import uuid4
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.api.app import create_app
from src.storage.database import Base
from src.api.dependencies import get_db_session


# Create test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create a fresh test database for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    yield override_get_db, engine

    await engine.dispose()


@pytest.fixture
async def client(test_db):
    """Create test client with mocked auth."""
    override_get_db, engine = test_db
    app = create_app()

    # Override database dependency
    app.dependency_overrides[get_db_session] = override_get_db

    # Register test tenant for auth
    from uuid import UUID
    from datetime import datetime
    from src.api.middleware.auth import hash_api_key, _tenant_store

    test_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    key_hash = hash_api_key("test_key")
    _tenant_store[key_hash] = {
        "tenant_id": test_tenant_id,
        "name": "test",
        "is_active": True,
        "created_at": datetime.utcnow(),
        "projects_count": 0,
        "pages_this_month": 0,
        "usage_reset_at": datetime.utcnow(),
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["X-API-Key"] = "test_key"
        yield ac

    # Cleanup
    if key_hash in _tenant_store:
        del _tenant_store[key_hash]


@pytest.fixture
async def project_id(client):
    """Create a test project."""
    resp = await client.post("/projects")
    assert resp.status_code == 201
    return resp.json()["id"]


def create_pdf_with_pages(num_pages: int) -> bytes:
    """Create a real PDF with specified number of pages using PyMuPDF."""
    import fitz
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=612, height=792)  # Letter size
        page.insert_text((72, 72), f"Page {i + 1}", fontsize=24)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestPDFUpload:
    """Tests for POST /v3/projects/{project_id}/pdf"""

    @pytest.mark.asyncio
    async def test_upload_valid_pdf(self, client, project_id):
        """Test uploading a valid PDF file."""
        # Create a real 1-page PDF using PyMuPDF
        pdf_content = create_pdf_with_pages(1)

        resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["schema_version"] == "3.1"
        assert data["project_id"] == project_id
        assert "pdf_id" in data
        assert "fingerprint" in data
        assert data["page_count"] == 1

    @pytest.mark.asyncio
    async def test_upload_pdf_page_count_exact(self, client, project_id):
        """Test that page_count is computed correctly using PyMuPDF."""
        # Create a 3-page PDF
        pdf_content = create_pdf_with_pages(3)

        resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test_3pages.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["page_count"] == 3, f"Expected 3 pages, got {data['page_count']}"

    @pytest.mark.asyncio
    async def test_upload_invalid_pdf(self, client, project_id):
        """Test uploading an invalid file returns 400."""
        resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
        )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error_code"] == "INVALID_PDF"

    @pytest.mark.asyncio
    async def test_upload_to_nonexistent_project(self, client):
        """Test uploading to nonexistent project returns 404."""
        fake_project_id = str(uuid4())
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\ntrailer\n%%EOF"

        resp = await client.post(
            f"/v3/projects/{fake_project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )

        assert resp.status_code == 404


class TestBuildMapping:
    """Tests for POST /v3/projects/{project_id}/pdf/{pdf_id}/build-mapping"""

    @pytest.fixture
    async def pdf_id(self, client, project_id):
        """Upload a PDF and return its ID."""
        pdf_content = create_pdf_with_pages(1)
        resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        return resp.json()["pdf_id"]

    @pytest.mark.asyncio
    async def test_build_mapping_success(self, client, project_id, pdf_id):
        """Test starting a mapping job."""
        resp = await client.post(
            f"/v3/projects/{project_id}/pdf/{pdf_id}/build-mapping"
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["schema_version"] == "3.1"
        assert data["project_id"] == project_id
        assert data["pdf_id"] == pdf_id
        assert "mapping_job_id" in data
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_build_mapping_pdf_not_found(self, client, project_id):
        """Test mapping with nonexistent PDF returns 404."""
        fake_pdf_id = str(uuid4())
        resp = await client.post(
            f"/v3/projects/{project_id}/pdf/{fake_pdf_id}/build-mapping"
        )

        assert resp.status_code == 404
        assert resp.json()["error_code"] == "PDF_NOT_FOUND"


class TestMappingStatus:
    """Tests for GET /v3/projects/{project_id}/pdf/{pdf_id}/mapping/status"""

    @pytest.fixture
    async def mapping_setup(self, client, project_id):
        """Upload PDF and start mapping."""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\ntrailer\n%%EOF"
        pdf_resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        pdf_id = pdf_resp.json()["pdf_id"]

        mapping_resp = await client.post(
            f"/v3/projects/{project_id}/pdf/{pdf_id}/build-mapping"
        )
        return project_id, pdf_id, mapping_resp.json()["mapping_job_id"]

    @pytest.mark.asyncio
    async def test_get_mapping_status(self, client, mapping_setup):
        """Test getting mapping status."""
        project_id, pdf_id, job_id = mapping_setup

        resp = await client.get(
            f"/v3/projects/{project_id}/pdf/{pdf_id}/mapping/status"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "3.1"
        assert data["overall_status"] in ["pending", "running", "completed", "failed"]
        assert "mapping_version_id" in data


class TestGetMapping:
    """Tests for GET /v3/projects/{project_id}/pdf/{pdf_id}/mapping"""

    @pytest.fixture
    async def completed_mapping(self, client, project_id):
        """Create completed mapping."""
        pdf_content = create_pdf_with_pages(1)
        pdf_resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        pdf_id = pdf_resp.json()["pdf_id"]

        await client.post(f"/v3/projects/{project_id}/pdf/{pdf_id}/build-mapping")
        return project_id, pdf_id

    @pytest.mark.asyncio
    async def test_get_mapping_metadata(self, client, completed_mapping):
        """Test getting mapping metadata."""
        project_id, pdf_id = completed_mapping

        resp = await client.get(f"/v3/projects/{project_id}/pdf/{pdf_id}/mapping")

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "3.1"
        assert "fingerprint" in data
        assert "mapping_version_id" in data
        assert "pages" in data
        assert len(data["pages"]) >= 1

        # Verify page mapping structure
        page = data["pages"][0]
        assert "page_number" in page
        assert "png_width" in page
        assert "png_height" in page
        assert "pdf_width_pt" in page
        assert "pdf_height_pt" in page
        assert "transform" in page
        assert len(page["transform"]["matrix"]) == 6

    @pytest.mark.asyncio
    async def test_get_mapping_without_build_returns_409(self, client, project_id):
        """Gate 2: Mapping required refusal."""
        pdf_content = create_pdf_with_pages(1)
        pdf_resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        pdf_id = pdf_resp.json()["pdf_id"]

        # Don't build mapping, try to get it
        resp = await client.get(f"/v3/projects/{project_id}/pdf/{pdf_id}/mapping")

        assert resp.status_code == 409
        assert resp.json()["error_code"] == "MAPPING_REQUIRED"


class TestRenderPDF:
    """Tests for POST /v3/projects/{project_id}/render/pdf"""

    @pytest.fixture
    async def render_setup(self, client, project_id):
        """Upload PDF and complete mapping."""
        pdf_content = create_pdf_with_pages(1)
        pdf_resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        pdf_data = pdf_resp.json()
        pdf_id = pdf_data["pdf_id"]

        await client.post(f"/v3/projects/{project_id}/pdf/{pdf_id}/build-mapping")

        # Get mapping version ID
        status_resp = await client.get(
            f"/v3/projects/{project_id}/pdf/{pdf_id}/mapping/status"
        )
        mapping_version_id = status_resp.json()["mapping_version_id"]

        return project_id, pdf_id, mapping_version_id

    @pytest.mark.asyncio
    async def test_render_pdf_success(self, client, render_setup):
        """Test rendering annotated PDF."""
        project_id, pdf_id, mapping_version_id = render_setup

        resp = await client.post(
            f"/v3/projects/{project_id}/render/pdf",
            json={
                "pdf_id": pdf_id,
                "mapping_version_id": mapping_version_id,
                "objects": ["room_203"],
                "style": {"mode": "highlight", "include_labels": True},
            },
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["schema_version"] == "3.1"
        assert "render_job_id" in data
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_render_pdf_mismatch(self, client, render_setup):
        """Gate 1: PDF mismatch refusal."""
        project_id, pdf_id, mapping_version_id = render_setup
        fake_pdf_id = str(uuid4())

        resp = await client.post(
            f"/v3/projects/{project_id}/render/pdf",
            json={
                "pdf_id": fake_pdf_id,
                "mapping_version_id": mapping_version_id,
                "objects": [],
            },
        )

        assert resp.status_code == 409
        assert resp.json()["error_code"] == "PDF_MISMATCH"

    @pytest.mark.asyncio
    async def test_render_mapping_required(self, client, project_id):
        """Gate 2: Mapping required refusal."""
        pdf_content = create_pdf_with_pages(1)
        pdf_resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        pdf_id = pdf_resp.json()["pdf_id"]
        fake_mapping_id = str(uuid4())

        resp = await client.post(
            f"/v3/projects/{project_id}/render/pdf",
            json={
                "pdf_id": pdf_id,
                "mapping_version_id": fake_mapping_id,
                "objects": [],
            },
        )

        assert resp.status_code == 409
        assert resp.json()["error_code"] == "MAPPING_REQUIRED"

    @pytest.mark.asyncio
    async def test_render_is_pure_no_model_calls(self, client, render_setup):
        """Gate 6: Renderer is pure (zero model calls)."""
        project_id, pdf_id, mapping_version_id = render_setup

        # Patch OpenAI client to fail if called
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.side_effect = AssertionError("Model call attempted in render!")

            resp = await client.post(
                f"/v3/projects/{project_id}/render/pdf",
                json={
                    "pdf_id": pdf_id,
                    "mapping_version_id": mapping_version_id,
                    "objects": ["room_203"],
                },
            )

            # Should succeed without calling OpenAI
            assert resp.status_code == 202


class TestRenderStatus:
    """Tests for GET /v3/projects/{project_id}/render/pdf/{render_job_id}"""

    @pytest.mark.asyncio
    async def test_get_render_status(self, client, project_id):
        """Test getting render job status."""
        # Setup
        pdf_content = create_pdf_with_pages(1)
        pdf_resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        pdf_id = pdf_resp.json()["pdf_id"]

        await client.post(f"/v3/projects/{project_id}/pdf/{pdf_id}/build-mapping")

        status_resp = await client.get(
            f"/v3/projects/{project_id}/pdf/{pdf_id}/mapping/status"
        )
        mapping_version_id = status_resp.json()["mapping_version_id"]

        render_resp = await client.post(
            f"/v3/projects/{project_id}/render/pdf",
            json={"pdf_id": pdf_id, "mapping_version_id": mapping_version_id},
        )
        render_job_id = render_resp.json()["render_job_id"]

        # Test
        resp = await client.get(
            f"/v3/projects/{project_id}/render/pdf/{render_job_id}"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "3.1"
        assert data["render_job_id"] == render_job_id
        assert data["status"] in ["processing", "completed", "failed"]
        if data["status"] == "completed":
            assert "output_pdf_url" in data
            assert "trace" in data


class TestRenderAnnotations:
    """Tests for POST /v3/projects/{project_id}/render/annotations"""

    @pytest.mark.asyncio
    async def test_render_annotations(self, client, project_id):
        """Test exporting annotations."""
        pdf_content = create_pdf_with_pages(1)
        pdf_resp = await client.post(
            f"/v3/projects/{project_id}/pdf",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        pdf_id = pdf_resp.json()["pdf_id"]

        await client.post(f"/v3/projects/{project_id}/pdf/{pdf_id}/build-mapping")

        status_resp = await client.get(
            f"/v3/projects/{project_id}/pdf/{pdf_id}/mapping/status"
        )
        mapping_version_id = status_resp.json()["mapping_version_id"]

        resp = await client.post(
            f"/v3/projects/{project_id}/render/annotations",
            json={
                "pdf_id": pdf_id,
                "mapping_version_id": mapping_version_id,
                "format": "json",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "3.1"
        assert data["format"] == "json"
        assert "annotations" in data
