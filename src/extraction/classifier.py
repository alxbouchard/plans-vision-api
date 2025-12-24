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

Goal:
Classify the page into exactly one of these types:
plan, schedule, notes, legend, detail

Important:
- 'unknown' is allowed ONLY if the page is unreadable or essentially blank.
- If the page is readable but mixed (plan + notes + title block), choose the DOMINANT type and lower confidence.

Definitions:
- plan: spatial layout is primary (rooms, walls, circulation), even if notes/title block are present.
- schedule: table/grid is primary.
- notes: paragraphs/lists of text are primary.
- legend: symbols with explanations are primary.
- detail: zoomed construction details/sections/callouts are primary.

Output ONLY valid JSON:
{
  "page_type": "plan|schedule|notes|legend|detail",
  "confidence": 0.0-1.0,
  "evidence": ["observable cues"]
}

Rules:
- Always choose one of the five types if the page is readable.
- Express uncertainty via confidence, NOT via 'unknown'.
- No markdown, no extra keys.
"""

CLASSIFIER_USER_PROMPT = """Classify this construction document page. Return ONLY JSON."""


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
                prompt=CLASSIFIER_USER_PROMPT,
                model="gpt-5.2-pro",
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            )

            # Parse response
            result = json.loads(response)
            page_type_str = result.get("page_type", "detail").lower()
            confidence = float(result.get("confidence", 0.5))

            # Map to enum - fallback to DETAIL (not UNKNOWN) for invalid types
            try:
                page_type = PageType(page_type_str)
                # If model returned unknown for a readable page, downgrade to detail
                if page_type == PageType.UNKNOWN:
                    logger.warning(
                        "classifier_returned_unknown_downgrading_to_detail",
                        page_id=str(page_id),
                    )
                    page_type = PageType.DETAIL
                    confidence = min(confidence, 0.2)
            except ValueError:
                logger.warning(
                    "invalid_page_type_fallback_to_detail",
                    page_id=str(page_id),
                    received=page_type_str,
                )
                page_type = PageType.DETAIL
                confidence = 0.2

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
                "classifier_parse_fallback",
                page_id=str(page_id),
                error=str(e),
            )
            # Fallback to detail with low confidence - do NOT return unknown
            return PageClassification(
                page_id=page_id,
                page_type=PageType.DETAIL,
                confidence=0.2,
                confidence_level=ConfidenceLevel.LOW,
            )
        except Exception as e:
            logger.error(
                "classifier_error_fallback",
                page_id=str(page_id),
                error=str(e),
            )
            # Do NOT raise - fallback to detail to avoid blocking pipeline
            return PageClassification(
                page_id=page_id,
                page_type=PageType.DETAIL,
                confidence=0.2,
                confidence_level=ConfidenceLevel.LOW,
            )
