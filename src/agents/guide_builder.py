"""Guide Builder Agent - Analyzes first page to create provisional guide."""

from dataclasses import dataclass
from typing import Optional

from src.config import get_settings
from src.logging import get_logger
from .client import VisionClient
from .prompts import get_guide_builder_system, get_guide_builder_prompt

logger = get_logger(__name__)


@dataclass
class GuideBuilderResult:
    """Result from the Guide Builder agent."""
    provisional_guide: str
    success: bool
    error: Optional[str] = None


class GuideBuilderAgent:
    """
    Agent that analyzes the first page of a project to build a provisional visual guide.

    Uses: gpt-5.2-pro with high/xhigh reasoning, high verbosity
    """

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()
        self.settings = get_settings()

    async def build_guide(self, image_bytes: bytes, project_id: str) -> GuideBuilderResult:
        """
        Analyze the first page and build a provisional visual guide.

        Args:
            image_bytes: PNG image bytes of page 1
            project_id: Project ID for logging

        Returns:
            GuideBuilderResult with the provisional guide or error
        """
        logger.info(
            "guide_builder_start",
            project_id=project_id,
            agent="guide_builder",
            step="build_guide",
        )

        try:
            response = await self.client.analyze_image(
                image_bytes=image_bytes,
                prompt=get_guide_builder_prompt(),
                model=self.settings.model_guide_builder,
                reasoning_effort="high",  # Could use xhigh for more complex plans
                verbosity="high",
                system_prompt=get_guide_builder_system(),
            )

            logger.info(
                "guide_builder_complete",
                project_id=project_id,
                agent="guide_builder",
                step="build_guide",
                status="success",
                guide_length=len(response),
            )

            return GuideBuilderResult(
                provisional_guide=response,
                success=True,
            )

        except Exception as e:
            logger.error(
                "guide_builder_error",
                project_id=project_id,
                agent="guide_builder",
                step="build_guide",
                status="error",
                error=str(e),
            )

            return GuideBuilderResult(
                provisional_guide="",
                success=False,
                error=str(e),
            )
