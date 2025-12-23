"""Page type classifier using vision model."""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from src.logging import get_logger
from src.models.entities import PageType, ConfidenceLevel, PageClassification
from src.agents.client import VisionClient

logger = get_logger(__name__)

# Classification prompt
CLASSIFIER_SYSTEM_PROMPT = """You are a construction plan page classifier.
Your task is to classify the type of page shown in the image.

Page types:
- plan: A floor plan, site plan, or architectural layout showing rooms, walls, and spaces
- schedule: A table or schedule listing items (door schedule, room schedule, finish schedule)
- notes: A page of written notes, specifications, or general instructions
- legend: A legend or key explaining symbols used in the drawings
- detail: A detailed section or construction detail drawing
- unknown: Cannot determine the page type

Output ONLY a valid JSON object with these fields:
{
    "page_type": "<one of: plan, schedule, notes, legend, detail, unknown>",
    "confidence": <float 0.0 to 1.0>,
    "reasoning": "<brief explanation>"
}

Be conservative. If uncertain, use "unknown" with lower confidence.
"""

CLASSIFIER_USER_PROMPT = """Classify this construction document page.
What type of page is this?

Return ONLY a JSON object with page_type, confidence, and reasoning."""


def _confidence_to_level(confidence: float) -> ConfidenceLevel:
    """Convert numeric confidence to level."""
    if confidence >= 0.8:
        return ConfidenceLevel.HIGH
    elif confidence >= 0.5:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


class PageClassifier:
    """Classifies page types using vision model."""

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()

    async def classify(
        self,
        page_id: UUID,
        image_bytes: bytes,
    ) -> PageClassification:
        """
        Classify a page's type based on its image content.

        Args:
            page_id: The page ID
            image_bytes: Raw PNG bytes of the page

        Returns:
            PageClassification with type, confidence, and level
        """
        import json

        try:
            response = await self.client.analyze_image(
                image_bytes=image_bytes,
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                user_prompt=CLASSIFIER_USER_PROMPT,
            )

            # Parse response
            result = json.loads(response)
            page_type_str = result.get("page_type", "unknown").lower()
            confidence = float(result.get("confidence", 0.5))

            # Map to enum
            try:
                page_type = PageType(page_type_str)
            except ValueError:
                logger.warning(
                    "invalid_page_type",
                    page_id=str(page_id),
                    received=page_type_str,
                )
                page_type = PageType.UNKNOWN

            classification = PageClassification(
                page_id=page_id,
                page_type=page_type,
                confidence=confidence,
                confidence_level=_confidence_to_level(confidence),
            )

            logger.info(
                "page_classified",
                page_id=str(page_id),
                page_type=page_type.value,
                confidence=confidence,
            )

            return classification

        except json.JSONDecodeError as e:
            logger.error(
                "classifier_invalid_json",
                page_id=str(page_id),
                error=str(e),
            )
            # Return unknown with low confidence on parse error
            return PageClassification(
                page_id=page_id,
                page_type=PageType.UNKNOWN,
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
            )
        except Exception as e:
            logger.error(
                "classifier_error",
                page_id=str(page_id),
                error=str(e),
            )
            raise
