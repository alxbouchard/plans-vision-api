"""Schedule/table extraction from schedule pages.

Per TEST_GATES_PHASE2.md Gate F:
- For a schedule page
- Extract table grid structure
- Ensure schedule extraction does not run on plan pages
"""

from __future__ import annotations

import json
from uuid import UUID
from typing import Optional

from src.logging import get_logger
from src.models.entities import ObjectType, ConfidenceLevel, ExtractedScheduleTable, Geometry, ScheduleRow
from src.agents.client import VisionClient
from .id_generator import generate_object_id

logger = get_logger(__name__)

# Schedule extraction prompt - bbox is [x, y, w, h]
SCHEDULE_EXTRACTOR_SYSTEM_PROMPT = """You are a construction schedule table extractor.
Your task is to identify and extract table/schedule information from schedule pages.

Common schedule types in construction documents:
- Door schedule: Lists door IDs, sizes, materials, hardware
- Room finish schedule: Lists room IDs with floor, wall, ceiling finishes
- Window schedule: Lists window IDs, sizes, types
- Equipment schedule: Lists equipment items and specifications

For each table visible in the page, extract:
- schedule_type: One of: door_schedule, room_schedule, window_schedule, finish_schedule, equipment_schedule, other
- title: The table title if visible
- bbox: Approximate bounding box [x, y, width, height] in pixels
- headers: List of column headers if visible
- rows: List of rows with cell values

Output ONLY a valid JSON object with a "schedules" array:
{
    "schedules": [
        {
            "schedule_type": "door_schedule",
            "title": "DOOR SCHEDULE",
            "bbox": [50, 100, 750, 500],
            "headers": ["DOOR", "SIZE", "TYPE", "HARDWARE"],
            "rows": [
                ["D1", "900x2100", "SINGLE", "HC-1"],
                ["D2", "1200x2100", "DOUBLE", "HC-2"]
            ],
            "confidence": 0.9,
            "reasoning": "Clear table with door IDs and hardware info"
        }
    ]
}

Rules:
- Only extract tables that appear to be schedules
- Be conservative - only extract what you can clearly identify
- If schedule_type is unclear, use "other"
- Bbox format is [x, y, width, height] where x,y is top-left corner
"""

SCHEDULE_EXTRACTOR_USER_PROMPT = """Extract all schedules/tables from this page.

Return a JSON object with a "schedules" array.
Only include tables that appear to be construction schedules."""


def _confidence_to_level(confidence: float) -> ConfidenceLevel:
    """Convert numeric confidence to level."""
    if confidence >= 0.8:
        return ConfidenceLevel.HIGH
    elif confidence >= 0.5:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


class ScheduleExtractor:
    """Extracts schedule/table objects from schedule pages."""

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()

    async def extract(
        self,
        page_id: UUID,
        image_bytes: bytes,
    ) -> list[ExtractedScheduleTable]:
        """
        Extract schedules/tables from a schedule page.

        Args:
            page_id: The page ID
            image_bytes: Raw PNG bytes of the page

        Returns:
            List of ExtractedScheduleTable for each detected schedule
        """
        try:
            response = await self.client.analyze_image(
                image_bytes=image_bytes,
                system_prompt=SCHEDULE_EXTRACTOR_SYSTEM_PROMPT,
                user_prompt=SCHEDULE_EXTRACTOR_USER_PROMPT,
            )

            # Parse response
            result = json.loads(response)
            schedules_data = result.get("schedules", [])

            extracted_schedules = []
            for schedule in schedules_data:
                try:
                    bbox_data = schedule.get("bbox", [0, 0, 100, 100])
                    if len(bbox_data) != 4:
                        logger.warning(
                            "invalid_schedule_bbox",
                            page_id=str(page_id),
                            bbox=bbox_data,
                        )
                        continue

                    confidence = float(schedule.get("confidence", 0.5))
                    confidence_level = _confidence_to_level(confidence)

                    # Skip low confidence schedules
                    if confidence_level == ConfidenceLevel.LOW:
                        logger.debug(
                            "skipping_low_confidence_schedule",
                            page_id=str(page_id),
                            confidence=confidence,
                        )
                        continue

                    schedule_type = schedule.get("schedule_type", "other")
                    title = schedule.get("title", "")
                    headers = schedule.get("headers", [])
                    raw_rows = schedule.get("rows", [])

                    # Build label
                    label = title if title else schedule_type

                    # Generate deterministic ID
                    x, y, w, h = [int(v) for v in bbox_data]
                    bbox_tuple = (x, y, x + w, y + h)  # Convert to x1,y1,x2,y2 for ID
                    object_id = generate_object_id(
                        page_id=page_id,
                        object_type=ObjectType.SCHEDULE_TABLE,
                        label=label,
                        bbox=bbox_tuple,
                        qualifier=schedule_type,
                    )

                    # Create geometry with bbox as [x, y, w, h]
                    geometry = Geometry(
                        type="bbox",
                        bbox=[x, y, w, h],
                    )

                    # Convert rows to ScheduleRow objects
                    rows = [
                        ScheduleRow(row_index=i, cells=row_cells)
                        for i, row_cells in enumerate(raw_rows)
                    ]

                    # Create extracted schedule table
                    extracted = ExtractedScheduleTable(
                        id=object_id,
                        page_id=page_id,
                        label=label,
                        geometry=geometry,
                        confidence=confidence,
                        confidence_level=confidence_level,
                        sources=["table_detected"],
                        headers=headers,
                        rows=rows,
                    )
                    extracted_schedules.append(extracted)

                    logger.debug(
                        "schedule_extracted",
                        page_id=str(page_id),
                        object_id=object_id,
                        schedule_type=schedule_type,
                        row_count=len(rows),
                        column_count=len(headers),
                    )

                except Exception as e:
                    logger.warning(
                        "schedule_parsing_error",
                        page_id=str(page_id),
                        error=str(e),
                        schedule_data=schedule,
                    )
                    continue

            logger.info(
                "schedules_extracted",
                page_id=str(page_id),
                count=len(extracted_schedules),
            )

            return extracted_schedules

        except json.JSONDecodeError as e:
            logger.error(
                "schedule_extractor_invalid_json",
                page_id=str(page_id),
                error=str(e),
            )
            return []
        except Exception as e:
            logger.error(
                "schedule_extractor_error",
                page_id=str(page_id),
                error=str(e),
            )
            raise
