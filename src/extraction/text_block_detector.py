"""Text block detection for Phase 3.3.

Per WORK_QUEUE_PHASE3_3.md:
- Ticket 3: TextBlock type with bbox and text validation
- Ticket 4: TextBlockDetector stub returning []
- Ticket 5: Vision implementation

Constraints:
- No hardcoded positions, styles, or PDF-specific rules
- All evidence must be observable from the image
- Output strict JSON, fail loudly on invalid response
"""

from __future__ import annotations

import json
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.logging import get_logger
from src.agents.client import VisionClient

logger = get_logger(__name__)


# =============================================================================
# Vision prompts for text block detection
# =============================================================================

TEXT_BLOCK_SYSTEM_PROMPT = """You are analyzing a construction plan page to find text blocks.

Goal:
Locate all visible text blocks on the page that could be room labels, door numbers, or other identifiers.

Focus on:
- Room name blocks (e.g., "CLASSE", "BUREAU", "TOILET", "LOCAL")
- Room number blocks (e.g., "203", "A-101", "1.24")
- Combined label blocks (e.g., "CLASSE 203", "BUREAU 101")
- Door numbers near door symbols (e.g., "203", "203-1")

Do NOT include:
- Title blocks or page headers
- Scale indicators
- Dimension text
- General notes or paragraphs

Output ONLY valid JSON array:
[
  {
    "bbox": [x, y, width, height],
    "text": "detected text content",
    "confidence": 0.0-1.0
  }
]

Rules:
- bbox coordinates are in pixels from top-left corner
- Estimate approximate bounding box around each text block
- Multi-line text blocks should include all lines with newline characters
- confidence reflects how clearly the text was readable
- Return empty array [] if no relevant text blocks found
- No markdown, no extra keys, no explanation
"""

TEXT_BLOCK_USER_PROMPT = """Find all room labels, room numbers, and door numbers visible on this construction plan. Return ONLY a JSON array of text blocks with their approximate bounding boxes."""


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

    Stub mode (use_vision=False): returns empty list, no model calls.
    Vision mode (use_vision=True): uses GPT-5.2 to detect text blocks.
    """

    def __init__(self, use_vision: bool = False, client: Optional[VisionClient] = None):
        """Initialize detector.

        Args:
            use_vision: If True, use vision model for detection.
                       If False, return empty list (stub mode).
            client: Optional VisionClient instance (for testing).
        """
        self.use_vision = use_vision
        self.client = client

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

        Raises:
            ValueError: If vision response is not valid JSON
        """
        if not self.use_vision:
            # Stub mode: return empty list, no model calls
            logger.debug(
                "text_block_detector_stub",
                page_id=str(page_id),
                message="Stub mode: returning empty list",
            )
            return []

        logger.info(
            "phase3_3_detector_called",
            page_id=str(page_id),
        )

        # Initialize client if not provided
        client = self.client or VisionClient()

        try:
            # Call vision model
            response = await client.analyze_image(
                image_bytes=image_bytes,
                prompt=TEXT_BLOCK_USER_PROMPT,
                model="gpt-5.2-pro",
                system_prompt=TEXT_BLOCK_SYSTEM_PROMPT,
                reasoning_effort="medium",
                verbosity="low",
            )

            # Parse JSON response - fail loudly on invalid JSON
            try:
                raw_blocks = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(
                    "text_block_detector_invalid_json",
                    page_id=str(page_id),
                    error=str(e),
                    response_preview=response[:200] if response else "empty",
                )
                raise ValueError(f"Vision model returned invalid JSON: {e}")

            if not isinstance(raw_blocks, list):
                logger.error(
                    "text_block_detector_not_list",
                    page_id=str(page_id),
                    type=type(raw_blocks).__name__,
                )
                raise ValueError("Vision model did not return a JSON array")

            # Parse and validate each block
            text_blocks = []
            for i, raw in enumerate(raw_blocks):
                try:
                    block = TextBlock(
                        bbox=raw.get("bbox", [0, 0, 0, 0]),
                        text=raw.get("text", ""),
                        confidence=float(raw.get("confidence", 0.5)),
                    )

                    # Validate bbox within image bounds if dimensions provided
                    if image_width and image_height:
                        x, y, w, h = block.bbox
                        if x + w > image_width or y + h > image_height:
                            logger.warning(
                                "text_block_bbox_out_of_bounds",
                                page_id=str(page_id),
                                block_index=i,
                                bbox=block.bbox,
                                image_size=(image_width, image_height),
                            )
                            # Keep the block but note the warning

                    text_blocks.append(block)

                except Exception as e:
                    logger.warning(
                        "text_block_parse_error",
                        page_id=str(page_id),
                        block_index=i,
                        error=str(e),
                    )
                    # Skip invalid blocks, continue with others

            logger.info(
                "text_block_detector_result",
                page_id=str(page_id),
                blocks_detected=len(text_blocks),
            )

            return text_blocks

        except Exception as e:
            logger.error(
                "text_block_detector_error",
                page_id=str(page_id),
                error=str(e),
            )
            raise
