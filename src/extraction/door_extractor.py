"""Door extraction from plan pages.

Per TEST_GATES_PHASE2.md Gate E:
- At least 1 door object exists on plan pages
- Door_type may be unknown if not clear
- No doors extracted on non plan pages

Per PHASE2_DECISIONS.md:
- Output geometry is bbox only in Phase 2.0
- Prefer false negatives over false positives
"""

from __future__ import annotations

import json
from uuid import UUID
from typing import Optional

from src.logging import get_logger
from src.models.entities import ConfidenceLevel, DoorType, ExtractedDoor, Geometry
from src.agents.client import VisionClient
from .id_generator import generate_door_id

logger = get_logger(__name__)

# Door extraction prompt - bbox is [x, y, w, h]
DOOR_EXTRACTOR_SYSTEM_PROMPT = """You are a construction plan door extractor.
Your task is to identify and extract door information from floor plan images.

Door symbols in floor plans typically appear as:
- An arc showing the door swing
- A line representing the door leaf
- Sometimes accompanied by a door number/tag

For each door visible in the plan, extract:
- door_number: The number or ID shown (e.g., "D1", "101", null if not visible)
- door_type: One of: single, double, sliding, revolving, unknown
- bbox: Approximate bounding box [x, y, width, height] in pixels from top-left corner

Output ONLY a valid JSON object with a "doors" array:
{
    "doors": [
        {
            "door_number": "D1",
            "door_type": "single",
            "bbox": [150, 300, 30, 40],
            "confidence": 0.85,
            "reasoning": "Clear door swing symbol visible"
        }
    ]
}

Rules:
- Only extract where door symbol is clearly visible
- Be conservative - only extract what you can identify with confidence
- If door_number is not visible, use null
- door_type can be "unknown" if the type is not clear
- Bbox format is [x, y, width, height] where x,y is top-left corner
"""

DOOR_EXTRACTOR_USER_PROMPT = """Extract all doors from this floor plan.

Return a JSON object with a "doors" array.
Only include doors where you can clearly identify the door symbol."""


def _confidence_to_level(confidence: float) -> ConfidenceLevel:
    """Convert numeric confidence to level."""
    if confidence >= 0.8:
        return ConfidenceLevel.HIGH
    elif confidence >= 0.5:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


def _parse_door_type(door_type_str: Optional[str]) -> str:
    """Parse door type string to valid value."""
    if not door_type_str:
        return DoorType.UNKNOWN.value

    door_type_str = door_type_str.lower().strip()
    valid_types = {dt.value for dt in DoorType}
    if door_type_str in valid_types:
        return door_type_str
    return DoorType.UNKNOWN.value


class DoorExtractor:
    """Extracts door objects from plan pages."""

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()

    async def extract(
        self,
        page_id: UUID,
        image_bytes: bytes,
    ) -> list[ExtractedDoor]:
        """
        Extract doors from a plan page.

        Args:
            page_id: The page ID
            image_bytes: Raw PNG bytes of the page

        Returns:
            List of ExtractedDoor for each detected door
        """
        try:
            response = await self.client.analyze_image(
                image_bytes=image_bytes,
                system_prompt=DOOR_EXTRACTOR_SYSTEM_PROMPT,
                user_prompt=DOOR_EXTRACTOR_USER_PROMPT,
            )

            # Parse response
            result = json.loads(response)
            doors_data = result.get("doors", [])

            extracted_doors = []
            for door in doors_data:
                try:
                    bbox_data = door.get("bbox", [0, 0, 50, 50])
                    if len(bbox_data) != 4:
                        logger.warning(
                            "invalid_door_bbox",
                            page_id=str(page_id),
                            bbox=bbox_data,
                        )
                        continue

                    confidence = float(door.get("confidence", 0.5))
                    confidence_level = _confidence_to_level(confidence)

                    # Skip low confidence doors (per conservative extraction)
                    if confidence_level == ConfidenceLevel.LOW:
                        logger.debug(
                            "skipping_low_confidence_door",
                            page_id=str(page_id),
                            confidence=confidence,
                        )
                        continue

                    door_number = door.get("door_number")
                    door_type = _parse_door_type(door.get("door_type"))

                    # Build label
                    label = door_number if door_number else f"door_{door_type}"

                    # Generate deterministic ID
                    x, y, w, h = [int(v) for v in bbox_data]
                    bbox_tuple = (x, y, x + w, y + h)  # Convert to x1,y1,x2,y2 for ID
                    object_id = generate_door_id(
                        page_id=page_id,
                        label=label,
                        bbox=bbox_tuple,
                        door_number=door_number,
                    )

                    # Create geometry with bbox as [x, y, w, h]
                    geometry = Geometry(
                        type="bbox",
                        bbox=[x, y, w, h],
                    )

                    # Create extracted door
                    extracted = ExtractedDoor(
                        id=object_id,
                        page_id=page_id,
                        label=label,
                        geometry=geometry,
                        confidence=confidence,
                        confidence_level=confidence_level,
                        sources=["symbol_detected"],
                        door_type=door_type,
                    )
                    extracted_doors.append(extracted)

                    logger.debug(
                        "door_extracted",
                        page_id=str(page_id),
                        object_id=object_id,
                        door_number=door_number,
                        door_type=door_type,
                        confidence=confidence,
                    )

                except Exception as e:
                    logger.warning(
                        "door_parsing_error",
                        page_id=str(page_id),
                        error=str(e),
                        door_data=door,
                    )
                    continue

            logger.info(
                "doors_extracted",
                page_id=str(page_id),
                count=len(extracted_doors),
            )

            return extracted_doors

        except json.JSONDecodeError as e:
            logger.error(
                "door_extractor_invalid_json",
                page_id=str(page_id),
                error=str(e),
            )
            return []
        except Exception as e:
            logger.error(
                "door_extractor_error",
                page_id=str(page_id),
                error=str(e),
            )
            raise
