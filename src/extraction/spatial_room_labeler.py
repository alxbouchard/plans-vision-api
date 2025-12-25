"""Spatial room labeling for Phase 3.3.

Per FEATURE_Phase3_3_SpatialRoomLabeling.md:
- Identify candidate room label blocks based on guide payloads
- Use geometric evidence to distinguish rooms from doors
- Preserve ambiguity explicitly when evidence is insufficient

Constraints (non-negotiable):
- Zero hardcode of positions, styles, or PDF-specific rules
- All rules come from the guide payloads
- If no payloads, return 0 rooms and log 'no_machine_rules'
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
from src.agents.schemas import RulePayload, RuleKind
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
# Payload-based Token Detection
# =============================================================================

class TokenMatch(BaseModel):
    """A matched token from a text block."""
    token_type: str  # room_name, room_number, etc.
    value: str
    bbox: list[int]
    confidence: float


def apply_token_detector(
    block: TextBlockLike,
    payload: RulePayload,
) -> Optional[TokenMatch]:
    """Apply a token_detector payload to a text block.

    Returns a TokenMatch if the block matches the detector, None otherwise.
    """
    if payload.kind != RuleKind.TOKEN_DETECTOR:
        return None

    all_text = " ".join(block.text_lines)
    token_type = payload.token_type or "unknown"

    # Apply detector based on type
    if payload.detector == "regex" and payload.pattern:
        try:
            pattern = re.compile(payload.pattern, re.IGNORECASE)
            match = pattern.search(all_text)
            if match:
                return TokenMatch(
                    token_type=token_type,
                    value=match.group(0),
                    bbox=list(block.bbox),
                    confidence=block.confidence,
                )
        except re.error:
            logger.warning("invalid_regex_pattern", pattern=payload.pattern)
            return None

    elif payload.detector == "boxed_number":
        # Look for digits - "boxed" check would require visual analysis
        # For now, just detect number pattern
        number_pattern = payload.pattern or r"\d{1,4}"
        try:
            pattern = re.compile(number_pattern)
            match = pattern.search(all_text)
            if match:
                return TokenMatch(
                    token_type=token_type,
                    value=match.group(0),
                    bbox=list(block.bbox),
                    confidence=block.confidence,
                )
        except re.error:
            return None

    elif payload.detector == "ocr_keyword":
        # Check if any word in the pattern list matches
        if payload.pattern:
            keywords = [k.strip().upper() for k in payload.pattern.split("|")]
            words = all_text.upper().split()
            for word in words:
                if word in keywords:
                    return TokenMatch(
                        token_type=token_type,
                        value=word,
                        bbox=list(block.bbox),
                        confidence=block.confidence,
                    )

    # Check min_len if specified
    if payload.min_len:
        letter_tokens = re.findall(r'[A-Za-z]+', all_text)
        for token in letter_tokens:
            if len(token) >= payload.min_len:
                return TokenMatch(
                    token_type=token_type,
                    value=token,
                    bbox=list(block.bbox),
                    confidence=block.confidence,
                )

    return None


def should_exclude(
    block: TextBlockLike,
    exclude_payloads: list[RulePayload],
) -> tuple[bool, Optional[str]]:
    """Check if a block should be excluded based on exclude payloads.

    Returns (should_exclude, reason).
    """
    all_text = " ".join(block.text_lines).upper()

    for payload in exclude_payloads:
        if payload.kind != RuleKind.EXCLUDE:
            continue

        if payload.detector == "regex" and payload.pattern:
            try:
                pattern = re.compile(payload.pattern, re.IGNORECASE)
                if pattern.search(all_text):
                    return True, f"Matched exclude pattern: {payload.pattern}"
            except re.error:
                continue

    return False, None


# =============================================================================
# Spatial Room Labeler
# =============================================================================

class SpatialRoomLabeler:
    """Extracts rooms from text blocks using guide payloads.

    Reads machine-executable payloads from the guide and applies them.
    If no payloads are present, returns 0 rooms and logs 'no_machine_rules'.
    """

    def __init__(
        self,
        policy: ExtractionPolicy = ExtractionPolicy.CONSERVATIVE,
        door_proximity_threshold: float = 100.0,
        payloads: Optional[list[RulePayload]] = None,
    ):
        self.policy = policy
        self.door_proximity_threshold = door_proximity_threshold
        self.payloads = payloads or []

        # Categorize payloads
        self.room_name_detectors: list[RulePayload] = []
        self.room_number_detectors: list[RulePayload] = []
        self.exclude_rules: list[RulePayload] = []
        self.pairing_rules: list[RulePayload] = []

        for p in self.payloads:
            if p.kind == RuleKind.TOKEN_DETECTOR:
                if p.token_type == "room_name":
                    self.room_name_detectors.append(p)
                elif p.token_type == "room_number":
                    self.room_number_detectors.append(p)
            elif p.kind == RuleKind.EXCLUDE:
                self.exclude_rules.append(p)
            elif p.kind == RuleKind.PAIRING:
                self.pairing_rules.append(p)

    def extract_rooms(
        self,
        page_id: UUID,
        text_blocks: list[TextBlockLike],
        door_symbols: Optional[list[DoorSymbolLike]] = None,
    ) -> list[ExtractedRoom]:
        """Extract rooms from detected text blocks using guide payloads.

        Args:
            page_id: The page ID
            text_blocks: List of detected text blocks
            door_symbols: Optional list of detected door symbols for disambiguation

        Returns:
            List of ExtractedRoom objects
        """
        door_symbols = door_symbols or []

        # Check if we have any machine rules
        has_machine_rules = bool(
            self.room_name_detectors or
            self.room_number_detectors or
            self.exclude_rules
        )

        if not has_machine_rules:
            logger.info(
                "no_machine_rules",
                page_id=str(page_id),
                blocks_count=len(text_blocks),
                message="No payloads in guide, returning 0 rooms",
            )
            return []

        # Metrics
        tokens_found_by_type: dict[str, int] = {}
        pairs_formed = 0
        rejected_excluded = 0
        rejected_no_pair = 0

        extracted_rooms = []

        for block in text_blocks:
            try:
                # Step 1: Check exclusions
                excluded, reason = should_exclude(block, self.exclude_rules)
                if excluded:
                    rejected_excluded += 1
                    logger.debug(
                        "block_excluded",
                        page_id=str(page_id),
                        text=" ".join(block.text_lines),
                        reason=reason,
                    )
                    continue

                # Step 2: Try to detect room_name
                room_name_match: Optional[TokenMatch] = None
                for detector in self.room_name_detectors:
                    match = apply_token_detector(block, detector)
                    if match:
                        room_name_match = match
                        tokens_found_by_type["room_name"] = tokens_found_by_type.get("room_name", 0) + 1
                        break

                # Step 3: Try to detect room_number
                room_number_match: Optional[TokenMatch] = None
                for detector in self.room_number_detectors:
                    match = apply_token_detector(block, detector)
                    if match:
                        room_number_match = match
                        tokens_found_by_type["room_number"] = tokens_found_by_type.get("room_number", 0) + 1
                        break

                # Step 4: We need at least a room_name to emit
                if not room_name_match:
                    rejected_no_pair += 1
                    continue

                # We have a room_name, optionally with room_number
                pairs_formed += 1

                # Step 5: Build room
                room = self._build_room(
                    page_id=page_id,
                    block=block,
                    room_name=room_name_match.value,
                    room_number=room_number_match.value if room_number_match else None,
                    door_symbols=door_symbols,
                )
                if room:
                    extracted_rooms.append(room)

            except Exception as e:
                logger.warning(
                    "spatial_labeler_block_error",
                    page_id=str(page_id),
                    error=str(e),
                )
                continue

        # Log metrics
        logger.info(
            "phase3_3_labeler_metrics",
            page_id=str(page_id),
            tokens_found_by_type=tokens_found_by_type,
            pairs_formed=pairs_formed,
            rejected_excluded=rejected_excluded,
            rejected_no_pair=rejected_no_pair,
            rooms_emitted=len(extracted_rooms),
        )

        return extracted_rooms

    def _build_room(
        self,
        page_id: UUID,
        block: TextBlockLike,
        room_name: str,
        room_number: Optional[str],
        door_symbols: list[DoorSymbolLike],
    ) -> Optional[ExtractedRoom]:
        """Build an ExtractedRoom from matched tokens."""

        # Check proximity to doors
        near_door = is_near_door_symbol(
            block.bbox, door_symbols, self.door_proximity_threshold
        )

        confidence_level = _confidence_to_level(block.confidence)

        # Handle low confidence
        if confidence_level == ConfidenceLevel.LOW:
            if self.policy == ExtractionPolicy.CONSERVATIVE:
                logger.debug(
                    "skipping_low_confidence_room_conservative",
                    page_id=str(page_id),
                    room_number=room_number,
                    confidence=block.confidence,
                )
                return None

        # Check for ambiguity
        ambiguity = False
        ambiguity_reason = None

        if near_door and confidence_level == ConfidenceLevel.LOW:
            ambiguity = True
            ambiguity_reason = "Low confidence block near door symbol"

        # Build label
        if room_name and room_number:
            label = f"{room_name} {room_number}"
        else:
            label = room_name

        # Generate deterministic ID
        x, y, w, h = block.bbox
        bbox_tuple = (x, y, x + w, y + h)
        object_id = generate_room_id(
            page_id=page_id,
            label=label,
            bbox=bbox_tuple,
            room_number=room_number,
        )

        geometry = Geometry(
            type="bbox",
            bbox=list(block.bbox),
        )

        sources = ["text_detected", "spatial_labeling", "guide_payload"]
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
            room_region_bbox=None,
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


# =============================================================================
# Legacy compatibility - will be removed once guide payloads are generated
# =============================================================================

def is_candidate_room_label(block: TextBlockLike) -> bool:
    """DEPRECATED: Legacy function for backward compatibility.

    This function should NOT be used in new code.
    Use SpatialRoomLabeler with payloads instead.
    """
    # Minimal check: has letters with length >= 2
    all_text = " ".join(block.text_lines)
    letter_tokens = re.findall(r'[A-Za-z]{2,}', all_text)
    return len(letter_tokens) > 0


def extract_room_number(block: TextBlockLike) -> Optional[str]:
    """Extract the room number from a text block."""
    all_text = " ".join(block.text_lines)
    match = re.search(r'\b(\d{2,4}(-\d+)?)\b', all_text)
    if match:
        return match.group(1)
    return None


def extract_room_name(block: TextBlockLike) -> Optional[str]:
    """Extract the room name from a text block."""
    all_text = " ".join(block.text_lines)
    match = re.search(r'\b([A-Za-z]+)\b', all_text)
    if match:
        return match.group(1)
    return None
