"""Text block detection for Phase 3.3.

Per WORK_QUEUE_PHASE3_3.md:
- Ticket 3: TextBlock type with bbox and text validation
- Ticket 4: TextBlockDetector stub returning []
- Ticket 5: Vision implementation (TODO)

Constraints:
- No hardcoded positions, styles, or PDF-specific rules
- All evidence must be observable from the image
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.logging import get_logger

logger = get_logger(__name__)


class TextBlock(BaseModel):
    """A detected text block with bounding box and text content.

    Attributes:
        bbox: Bounding box [x, y, width, height] in image coordinates
        text: The detected text content (non-empty)
        confidence: Detection confidence 0.0-1.0
    """

    bbox: list[int] = Field(min_length=4, max_length=4)
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @field_validator("bbox")
    @classmethod
    def validate_bbox_positive(cls, v: list[int]) -> list[int]:
        """Ensure bbox values are non-negative."""
        if any(val < 0 for val in v):
            raise ValueError("bbox values must be non-negative")
        return v

    @property
    def text_lines(self) -> list[str]:
        """Return text as lines for compatibility with SpatialRoomLabeler."""
        return self.text.split("\n")


class TextBlockDetector:
    """Detects text blocks on plan pages.

    Stub implementation returns empty list.
    Vision implementation (Ticket 5) will use model to detect text blocks.
    """

    def __init__(self, use_vision: bool = False):
        """Initialize detector.

        Args:
            use_vision: If True, use vision model for detection.
                       If False, return empty list (stub mode).
        """
        self.use_vision = use_vision

    async def detect(
        self,
        page_id: UUID,
        image_bytes: bytes,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
    ) -> list[TextBlock]:
        """Detect text blocks in an image.

        Args:
            page_id: The page ID for logging
            image_bytes: The image bytes
            image_width: Image width for validation (optional)
            image_height: Image height for validation (optional)

        Returns:
            List of detected TextBlock objects
        """
        if not self.use_vision:
            # Stub mode: return empty list, no model calls
            logger.debug(
                "text_block_detector_stub",
                page_id=str(page_id),
                message="Stub mode: returning empty list",
            )
            return []

        # Vision implementation will be added in Ticket 5
        # For now, return empty list
        logger.info(
            "phase3_3_detector_called",
            page_id=str(page_id),
        )
        return []
