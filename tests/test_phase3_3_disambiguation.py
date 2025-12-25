"""Tests for Phase 3.3 Spatial Room Labeling - Room vs Door Disambiguation.

Per TEST_GATES_PHASE3_3.md Gate 1:
Fixture must contain:
- Room label block "CLASSE 203" in room interior
- Door number "203" near a door
- Door number "203-1" near a door

Expect:
- room_number=203 extracted as room
- door_number 203 and 203-1 extracted as doors
- no conflation

Constraints (from user):
1. Zero hardcode of positions, styles, or PDF-specific rules
2. All must be deduced from visual guide or measurable geometric evidence
3. Outputs must remain conservative: if ambiguous, return ambiguous=true
4. Never choose arbitrarily
"""

import pytest
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# =============================================================================
# Synthetic Fixture: 203 Disambiguation Scenario
# =============================================================================

class SyntheticTextBlock(BaseModel):
    """A synthetic text block for testing.

    Represents detected text on a plan with:
    - bbox: location and size
    - text_lines: the actual text content
    - confidence: detection confidence
    - context_type: what the block is near (for fixture setup only, not used in detection)
    """
    bbox: list[int] = Field(min_length=4, max_length=4)
    text_lines: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    # Fixture metadata - NOT available to detector
    context_type: Optional[str] = Field(
        default=None,
        description="For fixture only: 'room_interior', 'near_door_arc', etc."
    )


class SyntheticDoorSymbol(BaseModel):
    """A synthetic door symbol for testing.

    Represents a door arc/swing on the plan.
    """
    bbox: list[int] = Field(min_length=4, max_length=4)
    door_type: str = "single"


def create_203_disambiguation_fixture():
    """Create the synthetic fixture for the 203 disambiguation scenario.

    Layout (conceptual):
    +--------------------------------------------------+
    |                                                  |
    |     [Room Interior]                              |
    |          CLASSE                                  |
    |           203           <-- room label           |
    |                                                  |
    |                                                  |
    +--------+    +--------------------------------+   |
             |    |                                |   |
      [Door] |    |  [Door]                        |   |
       203   |    |   203-1                        |   |
             |    |                                |   |

    The fixture provides:
    - 3 text blocks (CLASSE 203, 203, 203-1)
    - 2 door symbols (near blocks 2 and 3)
    - Geometric relationships that should disambiguate
    """
    text_blocks = [
        # Block 1: Room label "CLASSE 203" in room interior
        # Multi-line format typical of room labels
        SyntheticTextBlock(
            bbox=[200, 150, 100, 60],  # Centered in room area
            text_lines=["CLASSE", "203"],
            confidence=0.92,
            context_type="room_interior",
        ),
        # Block 2: Door number "203" near door arc
        SyntheticTextBlock(
            bbox=[50, 320, 30, 18],  # Near left door
            text_lines=["203"],
            confidence=0.88,
            context_type="near_door_arc",
        ),
        # Block 3: Door number "203-1" near door arc
        SyntheticTextBlock(
            bbox=[150, 320, 40, 18],  # Near right door
            text_lines=["203-1"],
            confidence=0.85,
            context_type="near_door_arc",
        ),
    ]

    door_symbols = [
        # Door 1: Near block 2
        SyntheticDoorSymbol(
            bbox=[45, 280, 40, 40],
        ),
        # Door 2: Near block 3
        SyntheticDoorSymbol(
            bbox=[145, 280, 40, 40],
        ),
    ]

    return {
        "text_blocks": text_blocks,
        "door_symbols": door_symbols,
        "expected_rooms": [
            {"room_number": "203", "room_name": "CLASSE", "from_block_index": 0}
        ],
        "expected_doors": [
            {"door_number": "203", "from_block_index": 1},
            {"door_number": "203-1", "from_block_index": 2},
        ],
    }


# =============================================================================
# Gate 1: Room label vs door number disambiguation
# =============================================================================

class TestGate1_RoomLabelVsDoorDisambiguation:
    """
    Gate 1: Room label vs door number disambiguation

    This is the CORE test for Phase 3.3.
    The fixture contains both room labels and door numbers with the same
    numeric identifier (203). The system must distinguish them using:

    1. Text block content: Room labels typically have letter + number
    2. Geometric context: Door numbers are near door symbols

    Zero hardcoding allowed - all rules derived from observable evidence.
    """

    @pytest.fixture
    def fixture_203(self):
        """The 203 disambiguation fixture."""
        return create_203_disambiguation_fixture()

    def test_fixture_has_expected_structure(self, fixture_203):
        """Verify the fixture is set up correctly."""
        assert len(fixture_203["text_blocks"]) == 3
        assert len(fixture_203["door_symbols"]) == 2
        assert len(fixture_203["expected_rooms"]) == 1
        assert len(fixture_203["expected_doors"]) == 2

    def test_room_label_has_letter_and_number_tokens(self, fixture_203):
        """Room label block must contain both letter and number tokens."""
        room_block = fixture_203["text_blocks"][0]

        # Multi-line: ["CLASSE", "203"]
        all_text = " ".join(room_block.text_lines)

        # Has letter token
        import re
        has_letter = bool(re.search(r'[A-Za-z]+', all_text))
        assert has_letter, f"Room label should have letter token: {all_text}"

        # Has number token
        has_number = bool(re.search(r'\d+', all_text))
        assert has_number, f"Room label should have number token: {all_text}"

    def test_door_numbers_are_number_only(self, fixture_203):
        """Door number blocks contain only numbers (possibly with hyphen)."""
        import re

        door_block_1 = fixture_203["text_blocks"][1]
        door_block_2 = fixture_203["text_blocks"][2]

        for block in [door_block_1, door_block_2]:
            all_text = " ".join(block.text_lines)
            # Should NOT have standalone letter tokens (A-Z as words)
            # "203-1" is OK, "A-101" would have letters
            has_standalone_letters = bool(re.search(r'\b[A-Za-z]+\b', all_text))
            assert not has_standalone_letters, f"Door number should not have letter words: {all_text}"

    def test_door_blocks_are_near_door_symbols(self, fixture_203):
        """Door number blocks should be geometrically near door symbols."""
        door_block_1 = fixture_203["text_blocks"][1]
        door_block_2 = fixture_203["text_blocks"][2]
        door_sym_1 = fixture_203["door_symbols"][0]
        door_sym_2 = fixture_203["door_symbols"][1]

        def blocks_are_near(block_bbox, door_bbox, threshold=100):
            """Check if block is within threshold pixels of door."""
            bx, by, bw, bh = block_bbox
            dx, dy, dw, dh = door_bbox

            # Center points
            block_cx = bx + bw / 2
            block_cy = by + bh / 2
            door_cx = dx + dw / 2
            door_cy = dy + dh / 2

            distance = ((block_cx - door_cx) ** 2 + (block_cy - door_cy) ** 2) ** 0.5
            return distance < threshold

        # Block 1 (door 203) near door symbol 1
        assert blocks_are_near(door_block_1.bbox, door_sym_1.bbox), \
            "Door number 203 should be near door symbol 1"

        # Block 2 (door 203-1) near door symbol 2
        assert blocks_are_near(door_block_2.bbox, door_sym_2.bbox), \
            "Door number 203-1 should be near door symbol 2"

    def test_room_block_not_near_door_symbols(self, fixture_203):
        """Room label block should NOT be near any door symbol."""
        room_block = fixture_203["text_blocks"][0]
        door_symbols = fixture_203["door_symbols"]

        def blocks_are_near(block_bbox, door_bbox, threshold=100):
            bx, by, bw, bh = block_bbox
            dx, dy, dw, dh = door_bbox
            block_cx = bx + bw / 2
            block_cy = by + bh / 2
            door_cx = dx + dw / 2
            door_cy = dy + dh / 2
            distance = ((block_cx - door_cx) ** 2 + (block_cy - door_cy) ** 2) ** 0.5
            return distance < threshold

        for door_sym in door_symbols:
            assert not blocks_are_near(room_block.bbox, door_sym.bbox), \
                "Room label should NOT be near any door symbol"


# =============================================================================
# Tests for candidate identification logic (to be implemented)
# =============================================================================

class TestCandidateRoomLabelIdentification:
    """Test the logic that identifies candidate room labels.

    Per FEATURE doc Step B:
    A block is a candidate room label if:
    - contains at least one token that looks like a room number (2-4 digits or digit-hyphen pattern)
    - AND contains at least one letter token in the same block
    - OR shows multi-line formatting typical of room label blocks

    This is NOT a hardcoded dictionary - it's a format rule.
    """

    def test_classe_203_is_candidate_room_label(self):
        """CLASSE 203 should be identified as candidate room label."""
        block = SyntheticTextBlock(
            bbox=[200, 150, 100, 60],
            text_lines=["CLASSE", "203"],
            confidence=0.92,
        )

        # This test will fail until is_candidate_room_label is implemented
        from src.extraction.spatial_room_labeler import is_candidate_room_label

        assert is_candidate_room_label(block) is True

    def test_number_only_is_not_candidate_room_label(self):
        """A number-only block should NOT be a candidate room label."""
        block = SyntheticTextBlock(
            bbox=[50, 320, 30, 18],
            text_lines=["203"],
            confidence=0.88,
        )

        from src.extraction.spatial_room_labeler import is_candidate_room_label

        assert is_candidate_room_label(block) is False

    def test_hyphenated_number_is_not_candidate_room_label(self):
        """A hyphenated number (like 203-1) should NOT be a candidate room label."""
        block = SyntheticTextBlock(
            bbox=[150, 320, 40, 18],
            text_lines=["203-1"],
            confidence=0.85,
        )

        from src.extraction.spatial_room_labeler import is_candidate_room_label

        assert is_candidate_room_label(block) is False

    def test_single_line_room_label_is_candidate(self):
        """CLASSE 203 on single line should also be candidate."""
        block = SyntheticTextBlock(
            bbox=[200, 150, 100, 30],
            text_lines=["CLASSE 203"],
            confidence=0.90,
        )

        from src.extraction.spatial_room_labeler import is_candidate_room_label

        assert is_candidate_room_label(block) is True


# =============================================================================
# Tests for disambiguation output
# =============================================================================

class TestDisambiguationOutput:
    """Test that disambiguation produces correct room vs door classification.

    Expected output:
    - room_number=203 extracted as room (from CLASSE 203 block)
    - door_number=203, 203-1 extracted as doors (from number-only blocks near door symbols)
    - no conflation between room and door
    """

    @pytest.fixture
    def fixture_203(self):
        return create_203_disambiguation_fixture()

    def test_extracts_one_room_from_classe_203(self, fixture_203):
        """Should extract exactly 1 room from the CLASSE 203 block."""
        from src.extraction.spatial_room_labeler import SpatialRoomLabeler

        text_blocks = fixture_203["text_blocks"]
        door_symbols = fixture_203["door_symbols"]
        page_id = uuid4()

        labeler = SpatialRoomLabeler()
        rooms = labeler.extract_rooms(
            page_id=page_id,
            text_blocks=text_blocks,
            door_symbols=door_symbols,
        )

        assert len(rooms) == 1
        assert rooms[0].room_number == "203"
        assert rooms[0].room_name == "CLASSE"

    def test_does_not_extract_door_numbers_as_rooms(self, fixture_203):
        """Door numbers (203, 203-1) should NOT be extracted as rooms."""
        from src.extraction.spatial_room_labeler import SpatialRoomLabeler

        text_blocks = fixture_203["text_blocks"]
        door_symbols = fixture_203["door_symbols"]
        page_id = uuid4()

        labeler = SpatialRoomLabeler()
        rooms = labeler.extract_rooms(
            page_id=page_id,
            text_blocks=text_blocks,
            door_symbols=door_symbols,
        )

        # Should only have the CLASSE 203 room, not 203 or 203-1
        room_numbers = [r.room_number for r in rooms]
        assert "203-1" not in room_numbers, "203-1 should be door, not room"
        # Note: 203 appears in both, but should only come from CLASSE block

    def test_room_has_label_bbox(self, fixture_203):
        """Extracted room should include label_bbox from the text block."""
        from src.extraction.spatial_room_labeler import SpatialRoomLabeler

        text_blocks = fixture_203["text_blocks"]
        door_symbols = fixture_203["door_symbols"]
        page_id = uuid4()

        labeler = SpatialRoomLabeler()
        rooms = labeler.extract_rooms(
            page_id=page_id,
            text_blocks=text_blocks,
            door_symbols=door_symbols,
        )

        assert len(rooms) == 1
        # label_bbox should match the CLASSE 203 block bbox
        assert rooms[0].label_bbox == [200, 150, 100, 60]


# =============================================================================
# Tests for ambiguity handling
# =============================================================================

class TestAmbiguityHandling:
    """Test that ambiguous cases are handled conservatively.

    Per constraints: if ambiguous, return ambiguous=true and explain why.
    Never choose arbitrarily.
    """

    def test_ambiguous_when_letter_unclear(self):
        """If letters are unreadable, should mark as ambiguous."""
        from src.extraction.spatial_room_labeler import SpatialRoomLabeler

        # Block with unclear text (marked by "???")
        ambiguous_block = SyntheticTextBlock(
            bbox=[200, 150, 100, 60],
            text_lines=["????", "203"],  # Unclear room name
            confidence=0.3,  # Low confidence
        )

        page_id = uuid4()
        labeler = SpatialRoomLabeler()
        rooms = labeler.extract_rooms(
            page_id=page_id,
            text_blocks=[ambiguous_block],
            door_symbols=[],
        )

        # Should either not extract OR mark as ambiguous
        if len(rooms) > 0:
            assert rooms[0].ambiguity is True
            assert rooms[0].ambiguity_reason is not None

    def test_number_near_door_not_extracted_as_room(self):
        """A number near a door should NOT be extracted as a room."""
        from src.extraction.spatial_room_labeler import SpatialRoomLabeler

        # Number-only block near a door
        number_block = SyntheticTextBlock(
            bbox=[50, 320, 30, 18],
            text_lines=["203"],
            confidence=0.88,
        )

        door_symbol = SyntheticDoorSymbol(
            bbox=[45, 280, 40, 40],
        )

        page_id = uuid4()
        labeler = SpatialRoomLabeler()
        rooms = labeler.extract_rooms(
            page_id=page_id,
            text_blocks=[number_block],
            door_symbols=[door_symbol],
        )

        # Should NOT extract as room
        assert len(rooms) == 0


# =============================================================================
# Gate 3: Feature flag safety (Ticket 1)
# =============================================================================

class TestGate3_FeatureFlag:
    """Test that Phase 3.3 feature flag defaults to False."""

    def test_feature_flag_default_false(self):
        """ENABLE_PHASE3_3_SPATIAL_LABELING must default to False."""
        from src.config import Settings

        # Create fresh settings (not cached) to test defaults
        settings = Settings()
        assert settings.enable_phase3_3_spatial_labeling is False

    def test_feature_flag_can_be_enabled(self, monkeypatch):
        """Feature flag can be enabled via environment variable."""
        from src.config import Settings

        monkeypatch.setenv("ENABLE_PHASE3_3_SPATIAL_LABELING", "true")
        settings = Settings()
        assert settings.enable_phase3_3_spatial_labeling is True


# =============================================================================
# Ticket 3: TextBlock type
# =============================================================================

class TestTextBlockType:
    """Test TextBlock type validation."""

    def test_text_block_valid(self):
        """TextBlock with valid bbox and text is accepted."""
        from src.extraction.text_block_detector import TextBlock

        block = TextBlock(
            bbox=[100, 200, 150, 50],
            text="CLASSE 203",
            confidence=0.9,
        )
        assert block.bbox == [100, 200, 150, 50]
        assert block.text == "CLASSE 203"
        assert block.confidence == 0.9

    def test_text_block_requires_4_element_bbox(self):
        """TextBlock bbox must have exactly 4 elements."""
        from src.extraction.text_block_detector import TextBlock
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            TextBlock(bbox=[100, 200], text="test", confidence=0.9)

    def test_text_block_requires_non_empty_text(self):
        """TextBlock text must not be empty."""
        from src.extraction.text_block_detector import TextBlock
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            TextBlock(bbox=[100, 200, 150, 50], text="", confidence=0.9)


# =============================================================================
# Ticket 4: TextBlockDetector stub
# =============================================================================

class TestTextBlockDetectorStub:
    """Test TextBlockDetector stub returns empty list."""

    def test_detector_is_callable(self):
        """TextBlockDetector.detect must be callable."""
        from src.extraction.text_block_detector import TextBlockDetector

        detector = TextBlockDetector()
        assert callable(detector.detect)

    @pytest.mark.asyncio
    async def test_detector_returns_list(self):
        """TextBlockDetector.detect returns a list."""
        from src.extraction.text_block_detector import TextBlockDetector

        detector = TextBlockDetector()
        result = await detector.detect(page_id=uuid4(), image_bytes=b"fake")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_stub_returns_empty_list(self):
        """Stub implementation returns empty list (no vision call)."""
        from src.extraction.text_block_detector import TextBlockDetector

        detector = TextBlockDetector()
        result = await detector.detect(page_id=uuid4(), image_bytes=b"fake")
        assert result == []


# =============================================================================
# Ticket 2 & 6: Pipeline hook behind feature flag
# =============================================================================

class TestPipelineHook:
    """Test that Phase 3.3 hook is in pipeline and respects feature flag."""

    def test_phase3_3_hook_exists_in_pipeline(self):
        """Pipeline has a Phase 3.3 spatial labeling hook point."""
        from src.extraction.pipeline import _run_phase3_3_spatial_labeling
        assert callable(_run_phase3_3_spatial_labeling)

    @pytest.mark.asyncio
    async def test_hook_skipped_when_flag_false(self, monkeypatch):
        """When flag is False, Phase 3.3 hook does nothing (no model calls)."""
        from src.extraction.pipeline import _run_phase3_3_spatial_labeling
        from src.config import Settings

        # Ensure flag is off
        monkeypatch.setenv("ENABLE_PHASE3_3_SPATIAL_LABELING", "false")

        page_id = uuid4()
        # Should return empty list and make no calls
        result = await _run_phase3_3_spatial_labeling(
            page_id=page_id,
            image_bytes=b"fake",
            doors=[],
            settings=Settings(),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_hook_called_when_flag_true(self, monkeypatch):
        """When flag is True, Phase 3.3 hook runs detector."""
        from src.extraction.pipeline import _run_phase3_3_spatial_labeling
        from src.config import Settings

        monkeypatch.setenv("ENABLE_PHASE3_3_SPATIAL_LABELING", "true")

        page_id = uuid4()
        # Stub still returns empty, but hook should run
        result = await _run_phase3_3_spatial_labeling(
            page_id=page_id,
            image_bytes=b"fake",
            doors=[],
            settings=Settings(),
        )
        # Result is list (could be empty from stub)
        assert isinstance(result, list)


# =============================================================================
# Ticket 5: TextBlockDetector vision implementation tests
# =============================================================================

class TestTextBlockDetectorVision:
    """Test TextBlockDetector with mocked vision client."""

    @pytest.mark.asyncio
    async def test_vision_detector_parses_valid_json(self):
        """Vision detector parses valid JSON response from model."""
        from src.extraction.text_block_detector import TextBlockDetector
        from unittest.mock import AsyncMock, MagicMock

        # Mock vision client
        mock_client = MagicMock()
        mock_client.analyze_image = AsyncMock(return_value='[{"bbox": [100, 200, 150, 50], "text": "CLASSE 203", "confidence": 0.9}]')

        detector = TextBlockDetector(use_vision=True, client=mock_client)
        result = await detector.detect(page_id=uuid4(), image_bytes=b"fake")

        assert len(result) == 1
        assert result[0].text == "CLASSE 203"
        assert result[0].bbox == [100, 200, 150, 50]
        assert result[0].confidence == 0.9

    @pytest.mark.asyncio
    async def test_vision_detector_handles_empty_array(self):
        """Vision detector handles empty array response."""
        from src.extraction.text_block_detector import TextBlockDetector
        from unittest.mock import AsyncMock, MagicMock

        mock_client = MagicMock()
        mock_client.analyze_image = AsyncMock(return_value='[]')

        detector = TextBlockDetector(use_vision=True, client=mock_client)
        result = await detector.detect(page_id=uuid4(), image_bytes=b"fake")

        assert result == []

    @pytest.mark.asyncio
    async def test_vision_detector_fails_on_invalid_json(self):
        """Vision detector raises ValueError on invalid JSON."""
        from src.extraction.text_block_detector import TextBlockDetector
        from unittest.mock import AsyncMock, MagicMock

        mock_client = MagicMock()
        mock_client.analyze_image = AsyncMock(return_value='not valid json')

        detector = TextBlockDetector(use_vision=True, client=mock_client)

        with pytest.raises(ValueError) as exc_info:
            await detector.detect(page_id=uuid4(), image_bytes=b"fake")

        assert "invalid JSON" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_vision_detector_fails_on_non_array(self):
        """Vision detector raises ValueError if response is not array."""
        from src.extraction.text_block_detector import TextBlockDetector
        from unittest.mock import AsyncMock, MagicMock

        mock_client = MagicMock()
        mock_client.analyze_image = AsyncMock(return_value='{"not": "array"}')

        detector = TextBlockDetector(use_vision=True, client=mock_client)

        with pytest.raises(ValueError) as exc_info:
            await detector.detect(page_id=uuid4(), image_bytes=b"fake")

        assert "JSON array" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_vision_detector_skips_invalid_blocks(self):
        """Vision detector skips blocks with invalid data."""
        from src.extraction.text_block_detector import TextBlockDetector
        from unittest.mock import AsyncMock, MagicMock

        # One valid, one with empty text (invalid)
        mock_client = MagicMock()
        mock_client.analyze_image = AsyncMock(return_value='[{"bbox": [100, 200, 150, 50], "text": "VALID", "confidence": 0.9}, {"bbox": [0, 0, 0, 0], "text": "", "confidence": 0.5}]')

        detector = TextBlockDetector(use_vision=True, client=mock_client)
        result = await detector.detect(page_id=uuid4(), image_bytes=b"fake")

        # Only the valid block should be included
        assert len(result) == 1
        assert result[0].text == "VALID"

    @pytest.mark.asyncio
    async def test_vision_detector_handles_multiple_blocks(self):
        """Vision detector parses multiple text blocks."""
        from src.extraction.text_block_detector import TextBlockDetector
        from unittest.mock import AsyncMock, MagicMock

        mock_client = MagicMock()
        mock_client.analyze_image = AsyncMock(return_value='''[
            {"bbox": [100, 200, 150, 50], "text": "CLASSE\\n203", "confidence": 0.92},
            {"bbox": [50, 320, 30, 18], "text": "203", "confidence": 0.88},
            {"bbox": [150, 320, 40, 18], "text": "203-1", "confidence": 0.85}
        ]''')

        detector = TextBlockDetector(use_vision=True, client=mock_client)
        result = await detector.detect(page_id=uuid4(), image_bytes=b"fake")

        assert len(result) == 3
        assert result[0].text == "CLASSE\n203"
        assert result[0].text_lines == ["CLASSE", "203"]
        assert result[1].text == "203"
        assert result[2].text == "203-1"