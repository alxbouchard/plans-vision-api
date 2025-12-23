"""Room extraction from plan pages.

Per TEST_GATES_PHASE2.md Gate B:
- Extract produces at least 1 room object with:
  - room_number present
  - bbox present
  - confidence_level not low

Per PHASE2_DECISIONS.md:
- Output geometry is bbox only in Phase 2.0
- Prefer false negatives over false positives
"""

from __future__ import annotations

import json
from uuid import UUID
from typing import Optional

from src.logging import get_logger
from src.models.entities import ConfidenceLevel, ExtractedRoom, Geometry
from src.agents.client import VisionClient
from .id_generator import generate_room_id

logger = get_logger(__name__)

# Room extraction prompt - bbox is now [x, y, w, h]
ROOM_EXTRACTOR_SYSTEM_PROMPT = """You are a construction plan room extractor.
Your task is to identify and extract room information from floor plan images.

For each room visible in the plan, extract:
- room_number: The number or ID shown (e.g., "203", "B-101")
- room_name: The room type or name (e.g., "CLASSE", "BUREAU", "TOILET")
- bbox: Approximate bounding box [x, y, width, height] in pixels from top-left corner

Output ONLY a valid JSON object with a "rooms" array:
{
    "rooms": [
        {
            "room_number": "203",
            "room_name": "CLASSE",
            "bbox": [100, 200, 300, 150],
            "confidence": 0.9,
            "reasoning": "Clear room number and name visible"
        }
    ]
}

Rules:
- Only extract rooms where room_number is clearly visible
- Be conservative - only extract what you can read with confidence
- If room_name is not visible, use null
- Bbox format is [x, y, width, height] where x,y is top-left corner
- Confidence should reflect how clearly you can read the text
"""

ROOM_EXTRACTOR_USER_PROMPT = """Extract all rooms from this floor plan.

Return a JSON object with a "rooms" array.
Only include rooms where you can clearly read the room number."""


def _confidence_to_level(confidence: float) -> ConfidenceLevel:
    """Convert numeric confidence to level."""
    if confidence >= 0.8:
        return ConfidenceLevel.HIGH
    elif confidence >= 0.5:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


class RoomExtractor:
    """Extracts room objects from plan pages."""

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()

    async def extract(
        self,
        page_id: UUID,
        image_bytes: bytes,
    ) -> list[ExtractedRoom]:
        """
        Extract rooms from a plan page.

        Args:
            page_id: The page ID
            image_bytes: Raw PNG bytes of the page

        Returns:
            List of ExtractedRoom for each detected room
        """
        try:
            response = await self.client.analyze_image(
                image_bytes=image_bytes,
                system_prompt=ROOM_EXTRACTOR_SYSTEM_PROMPT,
                user_prompt=ROOM_EXTRACTOR_USER_PROMPT,
            )

            # Parse response
            result = json.loads(response)
            rooms_data = result.get("rooms", [])

            extracted_rooms = []
            for room in rooms_data:
                try:
                    room_number = room.get("room_number")
                    if not room_number:
                        # Skip rooms without number (per conservative rules)
                        continue

                    bbox_data = room.get("bbox", [0, 0, 100, 100])
                    if len(bbox_data) != 4:
                        logger.warning(
                            "invalid_room_bbox",
                            page_id=str(page_id),
                            bbox=bbox_data,
                        )
                        continue

                    confidence = float(room.get("confidence", 0.5))
                    confidence_level = _confidence_to_level(confidence)

                    # Skip low confidence rooms (per Gate B requirement)
                    if confidence_level == ConfidenceLevel.LOW:
                        logger.debug(
                            "skipping_low_confidence_room",
                            page_id=str(page_id),
                            room_number=room_number,
                            confidence=confidence,
                        )
                        continue

                    room_name = room.get("room_name")
                    label = f"{room_name} {room_number}" if room_name else room_number

                    # Generate deterministic ID using bbox corners for hashing
                    x, y, w, h = [int(v) for v in bbox_data]
                    bbox_tuple = (x, y, x + w, y + h)  # Convert to x1,y1,x2,y2 for ID
                    object_id = generate_room_id(
                        page_id=page_id,
                        label=label,
                        bbox=bbox_tuple,
                        room_number=room_number,
                    )

                    # Create geometry with bbox as [x, y, w, h]
                    geometry = Geometry(
                        type="bbox",
                        bbox=[x, y, w, h],
                    )

                    # Create extracted room
                    extracted = ExtractedRoom(
                        id=object_id,
                        page_id=page_id,
                        label=label,
                        geometry=geometry,
                        confidence=confidence,
                        confidence_level=confidence_level,
                        sources=["text_detected"],
                        room_number=room_number,
                        room_name=room_name,
                    )
                    extracted_rooms.append(extracted)

                    logger.debug(
                        "room_extracted",
                        page_id=str(page_id),
                        object_id=object_id,
                        room_number=room_number,
                        confidence=confidence,
                    )

                except Exception as e:
                    logger.warning(
                        "room_parsing_error",
                        page_id=str(page_id),
                        error=str(e),
                        room_data=room,
                    )
                    continue

            logger.info(
                "rooms_extracted",
                page_id=str(page_id),
                count=len(extracted_rooms),
            )

            return extracted_rooms

        except json.JSONDecodeError as e:
            logger.error(
                "room_extractor_invalid_json",
                page_id=str(page_id),
                error=str(e),
            )
            return []
        except Exception as e:
            logger.error(
                "room_extractor_error",
                page_id=str(page_id),
                error=str(e),
            )
            raise
