"""Guide Applier Agent - Tests provisional guide against subsequent pages."""

from dataclasses import dataclass
from typing import Optional

from src.config import get_settings
from src.logging import get_logger
from .client import VisionClient
from .prompts import GUIDE_APPLIER_SYSTEM, GUIDE_APPLIER_PROMPT

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result from validating a single page."""
    page_order: int
    validation_report: str
    success: bool
    error: Optional[str] = None


@dataclass
class GuideApplierResult:
    """Aggregated result from the Guide Applier agent."""
    page_validations: list[ValidationResult]
    all_success: bool


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
            prompt = GUIDE_APPLIER_PROMPT.format(
                provisional_guide=provisional_guide
            )

            response = await self.client.analyze_image(
                image_bytes=image_bytes,
                prompt=prompt,
                model=self.settings.model_guide_applier,
                reasoning_effort="low",  # Speed optimized for multiple pages
                verbosity="medium",
                system_prompt=GUIDE_APPLIER_SYSTEM,
            )

            logger.info(
                "guide_applier_complete",
                project_id=project_id,
                agent="guide_applier",
                step="validate_page",
                page=page_order,
                status="success",
            )

            return ValidationResult(
                page_order=page_order,
                validation_report=response,
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
                success=False,
                error=str(e),
            )

    async def validate_all_pages(
        self,
        pages: list[tuple[int, bytes]],  # (order, image_bytes)
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

        return GuideApplierResult(
            page_validations=validations,
            all_success=all_success,
        )
