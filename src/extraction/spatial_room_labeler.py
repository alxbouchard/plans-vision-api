"""Spatial room labeling for Phase 3.3.

Per FEATURE_Phase3_3_SpatialRoomLabeling.md:
- Identify candidate room label blocks based on text content
- Use geometric evidence to distinguish rooms from doors
- Preserve ambiguity explicitly when evidence is insufficient

Constraints (non-negotiable):
- Zero hardcode of positions, styles, or PDF-specific rules
- All must be deduced from visual guide or measurable geometric evidence
- If ambiguous, return ambiguity=true with reason
- Never choose arbitrarily
"""

from __future__ import annotations

import re
from uuid import UUID
from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from src.logging import get_logger
from src.models.entities import (
    ConfidenceLevel,
    ExtractionPolicy,
    ExtractedRoom,
    Geometry,
)
from .id_generator import generate_room_id

logger = get_logger(__name__)


# =============================================================================
# Text Block Protocol (used for testing with synthetic fixtures)
# =============================================================================

@runtime_checkable
class TextBlockLike(Protocol):
    """Protocol for text block objects."""
    bbox: list[int]
    text_lines: list[str]
    confidence: float


@runtime_checkable
class DoorSymbolLike(Protocol):
    """Protocol for door symbol objects."""
    bbox: list[int]


# =============================================================================
# Candidate Identification Logic
# =============================================================================

# Pattern for room numbers: 2-4 digits, or digit-hyphen pattern like 203-1
ROOM_NUMBER_PATTERN = re.compile(r'\b(\d{2,4}(-\d+)?)\b')

# Pattern for letter tokens (words with letters)
LETTER_TOKEN_PATTERN = re.compile(r'\b([A-Za-z]+)\b')

# Global annotations to exclude (NOT room names)
# These are drawing annotations, not spaces in the building
EXCLUDED_ANNOTATIONS = {
    # Orientation/scale
    "NORTH", "N", "SCALE", "ECHELLE", "NTS",
    # Detail/section markers
    "DETAIL", "SECTION", "COUPE", "ELEVATION", "ELEV",
    # Revision markers
    "REV", "REVISION", "DATE", "ISSUE",
    # Drawing info
    "DRAWING", "SHEET", "PAGE", "PLAN", "PLANS",
    "PROJECT", "PROJET", "CLIENT", "ARCHITECT",
    # Grid markers (single letters A-Z used for grids)
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    # Common non-room annotations
    "NOTE", "NOTES", "LEGEND", "LEGENDE", "KEY", "SEE", "VOIR",
    "TYPICAL", "TYP", "SIM", "SIMILAR", "EQ", "EQUAL",
    # Dimensions
    "MM", "CM", "M", "FT", "IN",
}

# Room type keywords that indicate this IS a room name
# These are functional descriptors of building spaces
ROOM_TYPE_KEYWORDS = {
    # French room types
    "CLASSE", "BUREAU", "CORRIDOR", "ESCALIER", "TOILETTE", "TOILETTES",
    "SALLE", "LOCAL", "RANGEMENT", "STOCKAGE", "ENTREE", "VESTIBULE",
    "CUISINE", "CAFETERIA", "GYMNASE", "BIBLIOTHEQUE", "LABORATOIRE",
    "SECRETARIAT", "DIRECTION", "RECEPTION", "ATTENTE", "REPOS",
    "MECANIQUE", "ELECTRIQUE", "JANITOR", "CONCIERGERIE",
    # English room types
    "CLASSROOM", "OFFICE", "HALLWAY", "STAIRWELL", "RESTROOM", "BATHROOM",
    "ROOM", "STORAGE", "CLOSET", "ENTRY", "LOBBY", "VESTIBULE",
    "KITCHEN", "CAFETERIA", "GYM", "GYMNASIUM", "LIBRARY", "LAB",
    "SECRETARY", "PRINCIPAL", "RECEPTION", "WAITING", "LOUNGE",
    "MECHANICAL", "ELECTRICAL", "JANITOR", "CUSTODIAN",
    # Generic
    "WC", "HC", "ACCESSIBLE",
}


def is_candidate_room_label(block: TextBlockLike) -> bool:
    """Determine if a text block is a candidate room label.

    A block is a candidate room label if:
    1. It contains a known room type keyword (CLASSE, BUREAU, CORRIDOR, etc.)
       - These are accepted even without a room number
    2. OR it contains both a letter token AND a room number pattern
    3. AND it is NOT an excluded annotation (NORTH, SCALE, DETAIL, etc.)

    This uses keyword matching for room types but excludes drawing annotations.

    Args:
        block: A text block with bbox, text_lines, and confidence

    Returns:
        True if the block is a candidate room label
    """
    # Join all text lines for analysis
    all_text = " ".join(block.text_lines).upper()

    # Extract all letter tokens
    letter_tokens = LETTER_TOKEN_PATTERN.findall(all_text.upper())

    # Check if any token is an excluded annotation
    for token in letter_tokens:
        if token.upper() in EXCLUDED_ANNOTATIONS:
            # If the ONLY token is an excluded annotation, reject
            if len(letter_tokens) == 1:
                return False

    # Check if any token is a known room type keyword
    for token in letter_tokens:
        if token.upper() in ROOM_TYPE_KEYWORDS:
            # Room type keyword found - this is a room label (with or without number)
            return True

    # Check for room number pattern (2-4 digits, optionally with hyphen suffix)
    has_room_number = bool(ROOM_NUMBER_PATTERN.search(all_text))

    # Check for letter tokens (at least one word with letters)
    has_letter_token = len(letter_tokens) > 0

    # Multi-line with letter on one line and number on another is also a candidate
    if len(block.text_lines) >= 2:
        first_line = block.text_lines[0].upper()
        second_line = block.text_lines[1].upper() if len(block.text_lines) > 1 else ""

        # Check if it's "CLASSE" + "203" style
        first_has_letter = bool(LETTER_TOKEN_PATTERN.search(first_line))
        second_has_number = bool(ROOM_NUMBER_PATTERN.search(second_line))

        if first_has_letter and second_has_number:
            return True

    # Standard check: must have both letter and number
    return has_letter_token and has_room_number


def extract_room_number(block: TextBlockLike) -> Optional[str]:
    """Extract the room number from a candidate room label block.

    Returns the first room number pattern found (2-4 digits, optionally with hyphen).
    """
    all_text = " ".join(block.text_lines)
    match = ROOM_NUMBER_PATTERN.search(all_text)
    if match:
        return match.group(1)
    return None


def extract_room_name(block: TextBlockLike) -> Optional[str]:
    """Extract the room name from a candidate room label block.

    Returns the first letter token found (e.g., CLASSE, BUREAU).
    """
    all_text = " ".join(block.text_lines)
    match = LETTER_TOKEN_PATTERN.search(all_text)
    if match:
        return match.group(1)
    return None


# =============================================================================
# Geometric Disambiguation
# =============================================================================

def _get_door_bbox(door) -> Optional[list[int]]:
    """Get bbox from a door object (handles both direct bbox and geometry.bbox)."""
    if hasattr(door, 'bbox') and door.bbox:
        return door.bbox
    if hasattr(door, 'geometry') and door.geometry and hasattr(door.geometry, 'bbox'):
        return door.geometry.bbox
    return None


def is_near_door_symbol(
    block_bbox: list[int],
    door_symbols: list,
    threshold: float = 100.0,
) -> bool:
    """Check if a text block is near any door symbol.

    Args:
        block_bbox: The text block bounding box [x, y, w, h]
        door_symbols: List of door symbols (with bbox or geometry.bbox)
        threshold: Maximum distance in pixels to be considered "near"

    Returns:
        True if the block is within threshold of any door symbol
    """
    if not door_symbols:
        return False

    bx, by, bw, bh = block_bbox
    block_cx = bx + bw / 2
    block_cy = by + bh / 2

    for door in door_symbols:
        door_bbox = _get_door_bbox(door)
        if not door_bbox:
            continue

        dx, dy, dw, dh = door_bbox
        door_cx = dx + dw / 2
        door_cy = dy + dh / 2

        distance = ((block_cx - door_cx) ** 2 + (block_cy - door_cy) ** 2) ** 0.5

        if distance < threshold:
            return True

    return False


def _confidence_to_level(confidence: float) -> ConfidenceLevel:
    """Convert numeric confidence to level."""
    if confidence >= 0.8:
        return ConfidenceLevel.HIGH
    elif confidence >= 0.5:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


# =============================================================================
# Spatial Room Labeler
# =============================================================================

class SpatialRoomLabeler:
    """Extracts rooms from text blocks using spatial evidence.

    Uses geometric relationships to distinguish room labels from door numbers.
    Preserves ambiguity explicitly when evidence is insufficient.
    """

    def __init__(
        self,
        policy: ExtractionPolicy = ExtractionPolicy.CONSERVATIVE,
        door_proximity_threshold: float = 100.0,
    ):
        self.policy = policy
        self.door_proximity_threshold = door_proximity_threshold

    def extract_rooms(
        self,
        page_id: UUID,
        text_blocks: list[TextBlockLike],
        door_symbols: Optional[list[DoorSymbolLike]] = None,
    ) -> list[ExtractedRoom]:
        """Extract rooms from detected text blocks.

        Args:
            page_id: The page ID
            text_blocks: List of detected text blocks
            door_symbols: Optional list of detected door symbols for disambiguation

        Returns:
            List of ExtractedRoom objects
        """
        door_symbols = door_symbols or []
        extracted_rooms = []

        for block in text_blocks:
            try:
                room = self._process_block(page_id, block, door_symbols)
                if room is not None:
                    extracted_rooms.append(room)
            except Exception as e:
                logger.warning(
                    "spatial_labeler_block_error",
                    page_id=str(page_id),
                    error=str(e),
                )
                continue

        logger.info(
            "spatial_rooms_extracted",
            page_id=str(page_id),
            count=len(extracted_rooms),
            policy=self.policy.value,
        )

        return extracted_rooms

    def _process_block(
        self,
        page_id: UUID,
        block: TextBlockLike,
        door_symbols: list[DoorSymbolLike],
    ) -> Optional[ExtractedRoom]:
        """Process a single text block for room extraction.

        Returns None if the block should not be extracted as a room.
        """
        # Step 1: Check if it's a candidate room label
        if not is_candidate_room_label(block):
            logger.debug(
                "block_not_candidate_room_label",
                page_id=str(page_id),
                text=" ".join(block.text_lines),
            )
            return None

        # Step 2: Check proximity to door symbols
        # If the block is near a door, it might be a door number, not a room label
        # However, room labels like "CLASSE 203" can be near doors
        # The key is: room labels have LETTER + NUMBER, door numbers have NUMBER only
        # Since we already checked is_candidate_room_label (which requires letters),
        # we can proceed. But we note proximity for context.
        near_door = is_near_door_symbol(
            block.bbox, door_symbols, self.door_proximity_threshold
        )

        # Step 3: Extract room number and name
        room_number = extract_room_number(block)
        room_name = extract_room_name(block)

        # Room name alone is valid (e.g., "CORRIDOR", "ESCALIER")
        # Room number alone is NOT valid (could be door number)
        if not room_name:
            logger.debug(
                "no_room_name_found",
                page_id=str(page_id),
                text=" ".join(block.text_lines),
            )
            return None

        # Step 4: Check confidence level
        confidence_level = _confidence_to_level(block.confidence)

        # Step 5: Handle low confidence
        if confidence_level == ConfidenceLevel.LOW:
            if self.policy == ExtractionPolicy.CONSERVATIVE:
                logger.debug(
                    "skipping_low_confidence_room_conservative",
                    page_id=str(page_id),
                    room_number=room_number,
                    confidence=block.confidence,
                )
                return None
            # RELAXED policy: allow but flag
            logger.info(
                "accepting_low_confidence_room_relaxed",
                page_id=str(page_id),
                room_number=room_number,
                confidence=block.confidence,
            )

        # Step 6: Check for ambiguity
        ambiguity = False
        ambiguity_reason = None

        # If room name is unclear (contains non-letter chars), mark as ambiguous
        all_text = " ".join(block.text_lines)
        if room_name and not room_name.isalpha():
            ambiguity = True
            ambiguity_reason = f"Room name contains non-letter characters: {room_name}"

        # If near door and low confidence, mark as ambiguous
        if near_door and confidence_level == ConfidenceLevel.LOW:
            ambiguity = True
            ambiguity_reason = "Low confidence block near door symbol"

        # Step 7: Build the extracted room
        # Label: "ROOM_NAME ROOM_NUMBER" or just "ROOM_NAME" if no number
        if room_name and room_number:
            label = f"{room_name} {room_number}"
        elif room_name:
            label = room_name
        else:
            label = room_number or "UNKNOWN"

        # Generate deterministic ID
        x, y, w, h = block.bbox
        bbox_tuple = (x, y, x + w, y + h)
        object_id = generate_room_id(
            page_id=page_id,
            label=label,
            bbox=bbox_tuple,
            room_number=room_number,
        )

        # Geometry uses the label bbox
        geometry = Geometry(
            type="bbox",
            bbox=list(block.bbox),
        )

        # Build sources
        sources = ["text_detected", "spatial_labeling"]
        if self.policy == ExtractionPolicy.RELAXED:
            sources.append("extraction_policy:relaxed")
            sources.append("guide_source:provisional")

        room = ExtractedRoom(
            id=object_id,
            page_id=page_id,
            label=label,
            geometry=geometry,
            confidence=block.confidence,
            confidence_level=confidence_level,
            sources=sources,
            room_number=room_number,
            room_name=room_name,
            label_bbox=list(block.bbox),
            room_region_bbox=None,  # Phase 3.3 Task 3: will be set when region inference is implemented
            ambiguity=ambiguity,
            ambiguity_reason=ambiguity_reason,
        )

        logger.debug(
            "room_extracted_spatial",
            page_id=str(page_id),
            object_id=object_id,
            room_number=room_number,
            room_name=room_name,
            confidence=block.confidence,
            ambiguity=ambiguity,
        )

        return room
