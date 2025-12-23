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
