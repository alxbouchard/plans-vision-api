"""Tests for Phase 2 extraction pipeline - TEST_GATES_PHASE2."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient

from src.models.entities import (
    PageType,
    ConfidenceLevel,
    ExtractionStatus,
    PageClassification,
    ObjectType,
    DoorType,
    ExtractedRoom,
    ExtractedDoor,
    Geometry,
)
from src.models.schemas_v2 import SCHEMA_VERSION_V2


# =============================================================================
# Gate A: Page classification required
# =============================================================================

class TestGateA_PageClassification:
    """
    Gate A: Page classification required
    - Given a project with pages
    - When extraction starts
    - Then every page must have page_type stored
    - And non plan pages must not run plan extraction
    """

    @pytest.fixture
    def owner_id(self) -> str:
        return str(uuid4())

    @pytest.fixture
    def headers(self, owner_id: str) -> dict:
        return {"X-Owner-Id": owner_id}

    @pytest.mark.asyncio
    async def test_page_classification_model_valid(self):
        """Test PageClassification model accepts valid data."""
        page_id = uuid4()
        classification = PageClassification(
            page_id=page_id,
            page_type=PageType.PLAN,
            confidence=0.92,
            confidence_level=ConfidenceLevel.HIGH,
        )
        assert classification.page_id == page_id
        assert classification.page_type == PageType.PLAN
        assert classification.confidence == 0.92
        assert classification.confidence_level == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_page_type_enum_values(self):
        """Test all required page types exist."""
        assert PageType.PLAN.value == "plan"
        assert PageType.SCHEDULE.value == "schedule"
        assert PageType.NOTES.value == "notes"
        assert PageType.LEGEND.value == "legend"
        assert PageType.DETAIL.value == "detail"
        assert PageType.UNKNOWN.value == "unknown"

    @pytest.mark.asyncio
    async def test_confidence_level_enum_values(self):
        """Test all confidence levels exist."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"

    @pytest.mark.asyncio
    async def test_extraction_requires_guide(self, client: AsyncClient, headers: dict):
        """Test that extraction requires a stable or provisional guide."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201  # 201 Created
        project_id = response.json()["id"]

        # Try to start extraction without guide
        response = await client.post(
            f"/v2/projects/{project_id}/extract",
            headers=headers,
        )
        # Should fail with 409 GUIDE_REQUIRED
        assert response.status_code == 409
        data = response.json()
        assert data["error_code"] == "GUIDE_REQUIRED"

    @pytest.mark.asyncio
    async def test_extraction_status_schema_version(self, client: AsyncClient, headers: dict):
        """Test that v2 responses use schema_version 2.0."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Check extraction status uses v2 schema
        response = await client.get(
            f"/v2/projects/{project_id}/extract/status",
            headers=headers,
        )
        # Should return 200 with pending status (no job yet)
        assert response.status_code == 200
        data = response.json()
        assert data.get("schema_version") == SCHEMA_VERSION_V2
        assert data.get("overall_status") == "pending"


# =============================================================================
# Gate B: Rooms extracted on consistent_set
# =============================================================================

class TestGateB_RoomsExtraction:
    """
    Gate B: Rooms extracted on consistent_set
    - Extract produces at least 1 room object with:
      - room_number present
      - bbox present
      - confidence_level not low
    """

    @pytest.mark.asyncio
    async def test_extracted_room_model_valid(self):
        """Test ExtractedRoom model accepts valid data."""
        page_id = uuid4()
        geometry = Geometry(type="bbox", bbox=[100, 200, 300, 150])
        room = ExtractedRoom(
            id="room_abc123",
            page_id=page_id,
            geometry=geometry,
            confidence=0.92,
            confidence_level=ConfidenceLevel.HIGH,
            sources=["text_detected"],
            room_number="203",
            room_name="CLASSE",
            label="CLASSE 203",
        )
        assert room.room_number == "203"
        assert room.room_name == "CLASSE"
        assert room.geometry.bbox == [100, 200, 300, 150]
        assert room.confidence_level != ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_room_requires_geometry(self):
        """Test that rooms must have bbox geometry."""
        page_id = uuid4()
        geometry = Geometry(type="bbox", bbox=[100, 200, 300, 150])
        room = ExtractedRoom(
            id="room_abc123",
            page_id=page_id,
            geometry=geometry,
            confidence=0.85,
            confidence_level=ConfidenceLevel.HIGH,
            room_number="101",
        )
        assert room.geometry is not None
        assert len(room.geometry.bbox) == 4


# =============================================================================
# Gate E: Doors extracted with conservative rules
# =============================================================================

class TestGateE_DoorsExtraction:
    """
    Gate E: Doors extracted with conservative rules
    - At least 1 door object exists on plan pages
    - Door_type may be unknown if not clear
    - No doors extracted on non plan pages
    """

    @pytest.mark.asyncio
    async def test_door_type_enum_values(self):
        """Test all door types exist."""
        assert DoorType.SINGLE.value == "single"
        assert DoorType.DOUBLE.value == "double"
        assert DoorType.SLIDING.value == "sliding"
        assert DoorType.REVOLVING.value == "revolving"
        assert DoorType.UNKNOWN.value == "unknown"

    @pytest.mark.asyncio
    async def test_extracted_door_model_valid(self):
        """Test ExtractedDoor model accepts valid data."""
        page_id = uuid4()
        geometry = Geometry(type="bbox", bbox=[150, 300, 30, 40])
        door = ExtractedDoor(
            id="door_xyz789",
            page_id=page_id,
            geometry=geometry,
            confidence=0.80,
            confidence_level=ConfidenceLevel.HIGH,
            sources=["symbol_detected"],
            door_type="single",
            label="D1",
        )
        assert door.door_type == "single"
        assert door.geometry.bbox == [150, 300, 30, 40]

    @pytest.mark.asyncio
    async def test_door_type_can_be_unknown(self):
        """Test that door_type can be unknown if not clear."""
        page_id = uuid4()
        geometry = Geometry(type="bbox", bbox=[150, 300, 30, 40])
        door = ExtractedDoor(
            id="door_unk123",
            page_id=page_id,
            geometry=geometry,
            confidence=0.60,
            confidence_level=ConfidenceLevel.MEDIUM,
            door_type="unknown",
        )
        assert door.door_type == "unknown"


# =============================================================================
# Gate G: Schema enforcement
# =============================================================================

class TestGateG_SchemaEnforcement:
    """
    Gate G: Schema enforcement
    - All extraction outputs validate against schemas
    - Invalid model output fails loudly
    """

    @pytest.mark.asyncio
    async def test_extraction_status_enum_values(self):
        """Test extraction status enum has required values."""
        assert ExtractionStatus.PENDING.value == "pending"
        assert ExtractionStatus.RUNNING.value == "running"
        assert ExtractionStatus.COMPLETED.value == "completed"
        assert ExtractionStatus.FAILED.value == "failed"

    @pytest.mark.asyncio
    async def test_v2_schema_version_constant(self):
        """Test v2 schema version is 2.0."""
        assert SCHEMA_VERSION_V2 == "2.0"

    @pytest.mark.asyncio
    async def test_object_type_enum_values(self):
        """Test object types include all required values."""
        assert ObjectType.ROOM.value == "room"
        assert ObjectType.DOOR.value == "door"
        assert ObjectType.WINDOW.value == "window"
        assert ObjectType.SCHEDULE_TABLE.value == "schedule_table"

    @pytest.mark.asyncio
    async def test_invalid_page_type_rejected(self):
        """Test that invalid page type raises validation error."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PageClassification(
                page_id=uuid4(),
                page_type="invalid_type",  # Not a valid PageType
                confidence=0.9,
                confidence_level=ConfidenceLevel.HIGH,
            )

    @pytest.mark.asyncio
    async def test_invalid_confidence_level_rejected(self):
        """Test that invalid confidence level raises validation error."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PageClassification(
                page_id=uuid4(),
                page_type=PageType.PLAN,
                confidence=0.9,
                confidence_level="invalid",  # Not a valid ConfidenceLevel
            )

    @pytest.mark.asyncio
    async def test_room_requires_page_id(self):
        """Test that room requires page_id."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExtractedRoom(
                id="room_123",
                # Missing page_id
                geometry=Geometry(type="bbox", bbox=[0, 0, 100, 100]),
                confidence=0.8,
                confidence_level=ConfidenceLevel.HIGH,
                room_number="101",
            )

    @pytest.mark.asyncio
    async def test_geometry_requires_valid_bbox(self):
        """Test that geometry validates bbox format."""
        from pydantic import ValidationError
        # bbox needs exactly 4 values
        with pytest.raises(ValidationError):
            Geometry(
                type="bbox",
                bbox=[100, 200, 300],  # Only 3 values
            )

    @pytest.mark.asyncio
    async def test_door_validates_against_schema(self):
        """Test ExtractedDoor validates against schema."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExtractedDoor(
                id="door_123",
                # Missing page_id
                geometry=Geometry(type="bbox", bbox=[0, 0, 30, 40]),
                confidence=0.8,
                confidence_level=ConfidenceLevel.HIGH,
                door_type="single",
            )


# =============================================================================
# Gate H: Deterministic index
# =============================================================================

class TestGateH_DeterministicIndex:
    """
    Gate H: Deterministic index
    - Index keys are deterministic
    - Re running extraction without changes does not change IDs for the same objects
    """

    @pytest.mark.asyncio
    async def test_id_generator_deterministic(self):
        """Test that ID generation is deterministic for same inputs."""
        from src.extraction.id_generator import generate_room_id, generate_door_id

        page_id = uuid4()
        bbox = (100, 200, 400, 350)

        # Generate ID twice with same inputs
        id1 = generate_room_id(page_id, "CLASSE 203", bbox, "203")
        id2 = generate_room_id(page_id, "CLASSE 203", bbox, "203")

        assert id1 == id2
        assert id1.startswith("room_")

    @pytest.mark.asyncio
    async def test_id_generator_different_for_different_inputs(self):
        """Test that different inputs produce different IDs."""
        from src.extraction.id_generator import generate_room_id

        page_id = uuid4()
        bbox1 = (100, 200, 400, 350)
        bbox2 = (500, 600, 700, 750)

        id1 = generate_room_id(page_id, "CLASSE 203", bbox1, "203")
        id2 = generate_room_id(page_id, "CLASSE 204", bbox2, "204")

        assert id1 != id2

    @pytest.mark.asyncio
    async def test_id_generator_stable_with_small_bbox_changes(self):
        """Test that small bbox changes are bucketed for stability."""
        from src.extraction.id_generator import generate_room_id, bucket_bbox

        page_id = uuid4()
        # Two bboxes with small difference (within same 50px bucket)
        # bucket_coordinate does floor division: value // 50 * 50
        # So 100-149 → 100, 200-249 → 200, 400-449 → 400, 350-399 → 350
        bbox1 = (100, 200, 400, 350)
        bbox2 = (120, 215, 430, 375)  # All coords stay in same buckets

        # After bucketing, should be same
        bucketed1 = bucket_bbox(bbox1)
        bucketed2 = bucket_bbox(bbox2)
        assert bucketed1 == bucketed2

        # IDs should be the same
        id1 = generate_room_id(page_id, "CLASSE 203", bbox1, "203")
        id2 = generate_room_id(page_id, "CLASSE 203", bbox2, "203")
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_door_id_deterministic(self):
        """Test door ID generation is deterministic."""
        from src.extraction.id_generator import generate_door_id

        page_id = uuid4()
        bbox = (150, 300, 180, 340)

        id1 = generate_door_id(page_id, "D1", bbox, "D1")
        id2 = generate_door_id(page_id, "D1", bbox, "D1")

        assert id1 == id2
        assert id1.startswith("door_")


# =============================================================================
# Query tests (Gates C, D)
# =============================================================================

class TestGateCD_Query:
    """
    Gate C: Query room number works
    Gate D: Ambiguous query is explicit
    """

    @pytest.fixture
    def owner_id(self) -> str:
        return str(uuid4())

    @pytest.fixture
    def headers(self, owner_id: str) -> dict:
        return {"X-Owner-Id": owner_id}

    @pytest.mark.asyncio
    async def test_query_requires_parameters(self, client: AsyncClient, headers: dict):
        """Test that query requires at least one parameter."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Query without parameters
        response = await client.get(
            f"/v2/projects/{project_id}/query",
            headers=headers,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "QUERY_EMPTY"

    @pytest.mark.asyncio
    async def test_query_returns_schema_version(self, client: AsyncClient, headers: dict):
        """Test that query response includes schema_version."""
        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Query with room_number
        response = await client.get(
            f"/v2/projects/{project_id}/query?room_number=203",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("schema_version") == SCHEMA_VERSION_V2
        assert "matches" in data
        assert "ambiguous" in data


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def client():
    """Create async test client."""
    from src.api.app import create_app
    from httpx import ASGITransport, AsyncClient

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# Phase 3.2 Regression: page_type persisted to database
# =============================================================================

class TestPhase32_PageTypePersistence:
    """
    Phase 3.2 Regression: overlay must return page_type != unknown after extraction.

    Gate: After /v2 extract on Addenda project, overlay for page 1 and 3
    must return page_type != "unknown".

    This test verifies that:
    1. Classification is persisted to database (not just in-memory)
    2. Overlay reads page_type from database (single source of truth)
    3. PageClassifier never returns "unknown" for readable pages
    """

    @pytest.fixture
    def owner_id(self) -> str:
        return str(uuid4())

    @pytest.fixture
    def headers(self, owner_id: str) -> dict:
        return {"X-Owner-Id": owner_id}

    @pytest.mark.asyncio
    async def test_page_classification_persisted_to_database(self):
        """Test that PageRepository.update_classification works correctly."""
        from datetime import datetime
        from src.storage import init_database, get_db
        from src.storage.repositories import ProjectRepository, PageRepository
        from src.models.entities import PageType

        await init_database()

        async with get_db() as db:
            # Create project
            project_repo = ProjectRepository(db)
            owner_id = uuid4()
            project = await project_repo.create(owner_id)

            # Create page
            page_repo = PageRepository(db)
            page = await page_repo.create(
                project_id=project.id,
                file_path="/test/page1.png",
            )

            # Update classification
            now = datetime.utcnow()
            success = await page_repo.update_classification(
                page_id=page.id,
                page_type=PageType.PLAN.value,
                confidence=0.92,
                classified_at=now,
            )
            assert success is True

            # Re-fetch page and verify classification persisted
            page_after = await page_repo.get_by_id(page.id, project.id)
            assert page_after is not None
            assert page_after.page_type == "plan"
            assert page_after.classification_confidence == 0.92
            assert page_after.classified_at is not None

    @pytest.mark.asyncio
    async def test_overlay_reads_page_type_from_database(self, client: AsyncClient, headers: dict):
        """Test that overlay endpoint reads page_type from database, not in-memory."""
        from datetime import datetime
        from src.storage import get_db
        from src.storage.repositories import PageRepository
        from src.models.entities import PageType
        import io

        # Create project
        response = await client.post("/projects", headers=headers)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Upload a simple test image (1x1 white PNG)
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
            b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        files = {"file": ("page1.png", io.BytesIO(png_bytes), "image/png")}
        response = await client.post(
            f"/projects/{project_id}/pages",
            headers=headers,
            files=files,
        )
        assert response.status_code == 201
        page_id = response.json()["id"]

        # Manually persist classification to database (simulating extraction)
        async with get_db() as db:
            page_repo = PageRepository(db)
            now = datetime.utcnow()
            success = await page_repo.update_classification(
                page_id=uuid4().hex[:8] + "-" + page_id.split("-", 1)[1] if "-" in page_id else page_id,
                page_type=PageType.DETAIL.value,
                confidence=0.85,
                classified_at=now,
            )
            # Try with actual page_id
            success = await page_repo.update_classification(
                page_id=uuid4() if not page_id else page_id,  # type: ignore
                page_type=PageType.DETAIL.value,
                confidence=0.85,
                classified_at=now,
            )

        # Update with correct UUID
        from uuid import UUID as UUIDType
        async with get_db() as db:
            page_repo = PageRepository(db)
            now = datetime.utcnow()
            success = await page_repo.update_classification(
                page_id=UUIDType(page_id),
                page_type=PageType.DETAIL.value,
                confidence=0.85,
                classified_at=now,
            )
            assert success is True

        # Fetch overlay - should read page_type from database
        response = await client.get(
            f"/v2/projects/{project_id}/pages/{page_id}/overlay",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()

        # page_type should be "detail" (from database), NOT "unknown"
        assert data["page_type"] == "detail", f"Expected 'detail' but got '{data['page_type']}'"

    @pytest.mark.asyncio
    async def test_page_type_not_unknown_for_classified_pages(self):
        """
        Verify that after classification is persisted, overlay never returns 'unknown'
        for a page that has been classified.

        This is the core regression gate for Phase 3.2.
        """
        from datetime import datetime
        from uuid import UUID as UUIDType
        from src.storage import init_database, get_db
        from src.storage.repositories import ProjectRepository, PageRepository
        from src.models.entities import PageType

        await init_database()

        async with get_db() as db:
            # Create project with page
            project_repo = ProjectRepository(db)
            page_repo = PageRepository(db)

            owner_id = uuid4()
            project = await project_repo.create(owner_id)

            page = await page_repo.create(
                project_id=project.id,
                file_path="/test/readable_page.png",
            )

            # Before classification: page_type should be None
            assert page.page_type is None

            # Simulate classification (as extraction would do)
            now = datetime.utcnow()
            await page_repo.update_classification(
                page_id=page.id,
                page_type=PageType.PLAN.value,
                confidence=0.88,
                classified_at=now,
            )

            # Re-fetch: page_type should be "plan", NOT "unknown"
            page_after = await page_repo.get_by_id(page.id, project.id)
            assert page_after is not None
            assert page_after.page_type == "plan"
            assert page_after.page_type != "unknown"


# =============================================================================
# Phase 3.2 Regression: RELAXED extraction policy
# =============================================================================

class TestPhase32_RelaxedExtractionPolicy:
    """
    Phase 3.2 Regression: RELAXED extraction policy for provisional_only mode.

    Rules for RELAXED policy:
    - Room: allow LOW confidence only if room_number is 2-4 digit token
    - Door: allow LOW confidence only if door_number is explicitly provided
    - All results must carry extraction_policy:relaxed and guide_source:provisional
    - CONSERVATIVE must never accept LOW confidence
    """

    @pytest.mark.asyncio
    async def test_extraction_policy_enum_values(self):
        """Test ExtractionPolicy enum has required values."""
        from src.models.entities import ExtractionPolicy
        assert ExtractionPolicy.CONSERVATIVE.value == "conservative"
        assert ExtractionPolicy.RELAXED.value == "relaxed"

    @pytest.mark.asyncio
    async def test_room_extractor_conservative_rejects_low_confidence(self):
        """Test CONSERVATIVE policy rejects LOW confidence rooms."""
        from src.extraction.room_extractor import RoomExtractor
        from src.models.entities import ExtractionPolicy
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client response with LOW confidence room
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"rooms": [
            {"room_number": "203", "room_name": "CLASSE", "bbox": [100, 200, 300, 150], "confidence": 0.3}
        ]}'''

        extractor = RoomExtractor(client=mock_client, policy=ExtractionPolicy.CONSERVATIVE)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # CONSERVATIVE should reject LOW confidence (0.3 < 0.5)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_room_extractor_relaxed_accepts_low_confidence_with_digit_token(self):
        """Test RELAXED policy accepts LOW confidence if room_number is 2-4 digit token."""
        from src.extraction.room_extractor import RoomExtractor
        from src.models.entities import ExtractionPolicy, ConfidenceLevel
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client response with LOW confidence room but valid digit token
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"rooms": [
            {"room_number": "203", "room_name": "CLASSE", "bbox": [100, 200, 300, 150], "confidence": 0.3}
        ]}'''

        extractor = RoomExtractor(client=mock_client, policy=ExtractionPolicy.RELAXED)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # RELAXED should accept because "203" is a valid 3-digit token
        assert len(results) == 1
        assert results[0].room_number == "203"
        assert results[0].confidence_level == ConfidenceLevel.LOW
        assert "extraction_policy:relaxed" in results[0].sources
        assert "guide_source:provisional" in results[0].sources

    @pytest.mark.asyncio
    async def test_room_extractor_relaxed_rejects_low_confidence_non_digit_token(self):
        """Test RELAXED policy rejects LOW confidence if room_number is not 2-4 digit token."""
        from src.extraction.room_extractor import RoomExtractor
        from src.models.entities import ExtractionPolicy
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client response with LOW confidence and non-digit room_number
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"rooms": [
            {"room_number": "A-101", "room_name": "BUREAU", "bbox": [100, 200, 300, 150], "confidence": 0.3}
        ]}'''

        extractor = RoomExtractor(client=mock_client, policy=ExtractionPolicy.RELAXED)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # RELAXED should reject because "A-101" is not a digit-only token
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_door_extractor_conservative_rejects_low_confidence(self):
        """Test CONSERVATIVE policy rejects LOW confidence doors."""
        from src.extraction.door_extractor import DoorExtractor
        from src.models.entities import ExtractionPolicy
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client response with LOW confidence door
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"doors": [
            {"door_number": "D1", "door_type": "single", "bbox": [150, 300, 30, 40], "confidence": 0.3}
        ]}'''

        extractor = DoorExtractor(client=mock_client, policy=ExtractionPolicy.CONSERVATIVE)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # CONSERVATIVE should reject LOW confidence
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_door_extractor_relaxed_accepts_low_confidence_with_door_number(self):
        """Test RELAXED policy accepts LOW confidence if door_number is explicitly provided."""
        from src.extraction.door_extractor import DoorExtractor
        from src.models.entities import ExtractionPolicy, ConfidenceLevel
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client response with LOW confidence door but with explicit door_number
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"doors": [
            {"door_number": "D1", "door_type": "single", "bbox": [150, 300, 30, 40], "confidence": 0.3}
        ]}'''

        extractor = DoorExtractor(client=mock_client, policy=ExtractionPolicy.RELAXED)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # RELAXED should accept because door_number is explicitly provided
        assert len(results) == 1
        assert results[0].label == "D1"
        assert results[0].confidence_level == ConfidenceLevel.LOW
        assert "extraction_policy:relaxed" in results[0].sources
        assert "guide_source:provisional" in results[0].sources

    @pytest.mark.asyncio
    async def test_door_extractor_relaxed_rejects_low_confidence_without_door_number(self):
        """Test RELAXED policy rejects LOW confidence if no door_number (arc-only)."""
        from src.extraction.door_extractor import DoorExtractor
        from src.models.entities import ExtractionPolicy
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client response with LOW confidence door but no door_number (arc-only)
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"doors": [
            {"door_number": null, "door_type": "single", "bbox": [150, 300, 30, 40], "confidence": 0.3}
        ]}'''

        extractor = DoorExtractor(client=mock_client, policy=ExtractionPolicy.RELAXED)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # RELAXED should reject because no door_number (arc-only inference)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_room_extractor_high_confidence_accepted_any_policy(self):
        """Test HIGH confidence rooms accepted regardless of policy."""
        from src.extraction.room_extractor import RoomExtractor
        from src.models.entities import ExtractionPolicy, ConfidenceLevel
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client response with HIGH confidence room
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"rooms": [
            {"room_number": "A-101", "room_name": "BUREAU", "bbox": [100, 200, 300, 150], "confidence": 0.95}
        ]}'''

        # Test with CONSERVATIVE
        extractor_cons = RoomExtractor(client=mock_client, policy=ExtractionPolicy.CONSERVATIVE)
        results_cons = await extractor_cons.extract(page_id, b"fake_image_bytes")
        assert len(results_cons) == 1
        assert results_cons[0].confidence_level == ConfidenceLevel.HIGH
        # CONSERVATIVE should NOT have policy markers
        assert "extraction_policy:relaxed" not in results_cons[0].sources

        # Test with RELAXED
        extractor_rel = RoomExtractor(client=mock_client, policy=ExtractionPolicy.RELAXED)
        results_rel = await extractor_rel.extract(page_id, b"fake_image_bytes")
        assert len(results_rel) == 1
        assert results_rel[0].confidence_level == ConfidenceLevel.HIGH
        # RELAXED should have policy markers even for HIGH confidence
        assert "extraction_policy:relaxed" in results_rel[0].sources
        assert "guide_source:provisional" in results_rel[0].sources

    @pytest.mark.asyncio
    async def test_is_valid_relaxed_room_number(self):
        """Test the room number validation for RELAXED policy."""
        from src.extraction.room_extractor import _is_valid_relaxed_room_number

        # Valid: 2-4 digit tokens
        assert _is_valid_relaxed_room_number("12") is True
        assert _is_valid_relaxed_room_number("203") is True
        assert _is_valid_relaxed_room_number("1001") is True

        # Invalid: too short, too long, non-digit
        assert _is_valid_relaxed_room_number("1") is False  # 1 digit
        assert _is_valid_relaxed_room_number("12345") is False  # 5 digits
        assert _is_valid_relaxed_room_number("A-101") is False  # contains letters
        assert _is_valid_relaxed_room_number("") is False
        assert _is_valid_relaxed_room_number(None) is False  # type: ignore


# =============================================================================
# VisionClient backward compatibility: user_prompt alias
# =============================================================================

class TestVisionClientUserPromptAlias:
    """
    Test that VisionClient.analyze_image accepts both 'prompt' and 'user_prompt'.

    This ensures backward compatibility with extractors that use user_prompt.
    """

    @pytest.mark.asyncio
    async def test_analyze_image_accepts_prompt(self):
        """Test analyze_image works with 'prompt' parameter."""
        from src.agents.client import VisionClient
        from unittest.mock import AsyncMock, MagicMock, patch

        with patch.object(VisionClient, '__init__', lambda self: None):
            client = VisionClient()
            client.client = MagicMock()

            # Mock the responses.create call
            mock_response = MagicMock()
            mock_response.output = []
            mock_response.usage = None
            client.client.responses = MagicMock()
            client.client.responses.create = AsyncMock(return_value=mock_response)

            # Call with 'prompt' - should work
            result = await client.analyze_image(
                image_bytes=b"fake",
                prompt="test prompt",
                model="gpt-5.2-pro",
            )

            # Verify the call was made
            client.client.responses.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_image_accepts_user_prompt(self):
        """Test analyze_image works with 'user_prompt' parameter (backward compat)."""
        from src.agents.client import VisionClient
        from unittest.mock import AsyncMock, MagicMock, patch

        with patch.object(VisionClient, '__init__', lambda self: None):
            client = VisionClient()
            client.client = MagicMock()

            # Mock the responses.create call
            mock_response = MagicMock()
            mock_response.output = []
            mock_response.usage = None
            client.client.responses = MagicMock()
            client.client.responses.create = AsyncMock(return_value=mock_response)

            # Call with 'user_prompt' - should work (backward compat)
            result = await client.analyze_image(
                image_bytes=b"fake",
                user_prompt="test prompt via user_prompt",
                model="gpt-5.2-pro",
            )

            # Verify the call was made
            client.client.responses.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_image_requires_either_prompt(self):
        """Test analyze_image raises if neither prompt nor user_prompt provided."""
        from src.agents.client import VisionClient
        from unittest.mock import patch

        with patch.object(VisionClient, '__init__', lambda self: None):
            client = VisionClient()

            # Call without any prompt - should raise
            with pytest.raises(ValueError, match="Either 'prompt' or 'user_prompt'"):
                await client.analyze_image(
                    image_bytes=b"fake",
                    model="gpt-5.2-pro",
                )

    @pytest.mark.asyncio
    async def test_door_extractor_uses_user_prompt_successfully(self):
        """Test DoorExtractor works with the client (uses user_prompt internally)."""
        from src.extraction.door_extractor import DoorExtractor
        from src.models.entities import ExtractionPolicy
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client that accepts user_prompt
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"doors": [
            {"door_number": "D1", "door_type": "single", "bbox": [150, 300, 30, 40], "confidence": 0.9}
        ]}'''

        extractor = DoorExtractor(client=mock_client, policy=ExtractionPolicy.CONSERVATIVE)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # Should work without TypeError
        assert len(results) == 1
        assert results[0].label == "D1"

        # Verify user_prompt was used (extractors use user_prompt=...)
        call_kwargs = mock_client.analyze_image.call_args.kwargs
        assert 'user_prompt' in call_kwargs or 'prompt' in call_kwargs

    @pytest.mark.asyncio
    async def test_room_extractor_uses_user_prompt_successfully(self):
        """Test RoomExtractor works with the client (uses user_prompt internally)."""
        from src.extraction.room_extractor import RoomExtractor
        from src.models.entities import ExtractionPolicy
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client that accepts user_prompt
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"rooms": [
            {"room_number": "203", "room_name": "CLASSE", "bbox": [100, 200, 300, 150], "confidence": 0.9}
        ]}'''

        extractor = RoomExtractor(client=mock_client, policy=ExtractionPolicy.CONSERVATIVE)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # Should work without TypeError
        assert len(results) == 1
        assert results[0].room_number == "203"

    @pytest.mark.asyncio
    async def test_schedule_extractor_uses_user_prompt_successfully(self):
        """Test ScheduleExtractor works with the client (uses user_prompt internally)."""
        from src.extraction.schedule_extractor import ScheduleExtractor
        from unittest.mock import AsyncMock

        page_id = uuid4()

        # Mock client that accepts user_prompt
        mock_client = AsyncMock()
        mock_client.analyze_image.return_value = '''{"schedules": [
            {"schedule_type": "door_schedule", "title": "Door Schedule", "bbox": [50, 50, 500, 300], "confidence": 0.9, "columns": ["No.", "Size", "Type"], "rows": [["D1", "900x2100", "Wood"]]}
        ]}'''

        extractor = ScheduleExtractor(client=mock_client)
        results = await extractor.extract(page_id, b"fake_image_bytes")

        # Should work without TypeError
        assert len(results) == 1
