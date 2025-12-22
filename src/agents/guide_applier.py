"""Guide Applier Agent - Tests provisional guide against subsequent pages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from src.config import get_settings
from src.logging import get_logger
from .client import VisionClient
from .prompts import get_guide_applier_system, get_guide_applier_prompt
from .schemas import GuideApplierOutput, RuleValidationStatus

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result from validating a single page."""
    page_order: int
    validation_report: str
    structured_output: Optional[GuideApplierOutput] = None
    has_contradictions: bool = False
    success: bool = True
    error: Optional[str] = None


@dataclass
class GuideApplierResult:
    """Aggregated result from the Guide Applier agent."""
    page_validations: list[ValidationResult]
    all_success: bool
    any_contradictions: bool = False


class GuideApplierAgent:
    """
    Agent that tests a provisional guide against subsequent pages.

    Uses: gpt-5.2 with none/low reasoning, medium verbosity
    """

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()
        self.settings = get_settings()

    async def validate_page(
        self,
        image_bytes: bytes,
        provisional_guide: str,
        page_order: int,
        project_id: str,
    ) -> ValidationResult:
        """
        Validate the provisional guide against a single page.

        Args:
            image_bytes: PNG image bytes
            provisional_guide: The provisional guide text
            page_order: Page number for logging
            project_id: Project ID for logging

        Returns:
            ValidationResult with the validation report or error
        """
        logger.info(
            "guide_applier_start",
            project_id=project_id,
            agent="guide_applier",
            step="validate_page",
            page=page_order,
        )

        try:
            prompt = get_guide_applier_prompt().format(
                provisional_guide=provisional_guide,
                page_number=page_order,
            )

            response = await self.client.analyze_image(
                image_bytes=image_bytes,
                prompt=prompt,
                model=self.settings.model_guide_applier,
                reasoning_effort="low",
                verbosity="medium",
                system_prompt=get_guide_applier_system(),
            )

            # Parse JSON response
            structured_output = self._parse_response(response)

            # Check for contradictions
            has_contradictions = False
            if structured_output:
                has_contradictions = any(
                    v.status == RuleValidationStatus.CONTRADICTED
                    for v in structured_output.rule_validations
                )

            logger.info(
                "guide_applier_complete",
                project_id=project_id,
                agent="guide_applier",
                step="validate_page",
                page=page_order,
                status="success",
                has_contradictions=has_contradictions,
            )

            return ValidationResult(
                page_order=page_order,
                validation_report=response,
                structured_output=structured_output,
                has_contradictions=has_contradictions,
                success=True,
            )

        except Exception as e:
            logger.error(
                "guide_applier_error",
                project_id=project_id,
                agent="guide_applier",
                step="validate_page",
                page=page_order,
                status="error",
                error=str(e),
            )

            return ValidationResult(
                page_order=page_order,
                validation_report="",
                structured_output=None,
                has_contradictions=False,
                success=False,
                error=str(e),
            )

    async def validate_all_pages(
        self,
        pages: list[tuple[int, bytes]],
        provisional_guide: str,
        project_id: str,
    ) -> GuideApplierResult:
        """
        Validate the provisional guide against all subsequent pages.

        Args:
            pages: List of (page_order, image_bytes) tuples
            provisional_guide: The provisional guide text
            project_id: Project ID for logging

        Returns:
            GuideApplierResult with all validation results
        """
        validations = []
        all_success = True
        any_contradictions = False

        for page_order, image_bytes in pages:
            result = await self.validate_page(
                image_bytes=image_bytes,
                provisional_guide=provisional_guide,
                page_order=page_order,
                project_id=project_id,
            )
            validations.append(result)
            if not result.success:
                all_success = False
            if result.has_contradictions:
                any_contradictions = True

        return GuideApplierResult(
            page_validations=validations,
            all_success=all_success,
            any_contradictions=any_contradictions,
        )

    def _parse_response(self, response: str) -> Optional[GuideApplierOutput]:
        """Parse JSON response into structured output."""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            return GuideApplierOutput.model_validate(data)
        except Exception as e:
            logger.warning(
                "guide_applier_parse_warning",
                error=str(e),
                message="Could not parse structured output",
            )
            return None

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown code blocks."""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]

        return text
