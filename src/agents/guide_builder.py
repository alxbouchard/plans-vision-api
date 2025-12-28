"""Guide Builder Agent - Analyzes first page to create provisional guide."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from src.config import get_settings
from src.logging import get_logger
from .client import VisionClient
from .prompts import get_guide_builder_system, get_guide_builder_prompt
from .schemas import GuideBuilderOutput

logger = get_logger(__name__)


@dataclass
class GuideBuilderResult:
    """Result from the Guide Builder agent."""
    provisional_guide: str
    structured_output: Optional[GuideBuilderOutput] = None
    success: bool = True
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
                reasoning_effort="low",
                verbosity="low",
                system_prompt=get_guide_builder_system(),
            )

            # Parse JSON response
            structured_output = self._parse_response(response)

            # Validate no assumptions were made
            if structured_output and structured_output.assumptions:
                logger.warning(
                    "guide_builder_assumptions_detected",
                    project_id=project_id,
                    assumptions=structured_output.assumptions,
                )

            logger.info(
                "guide_builder_complete",
                project_id=project_id,
                agent="guide_builder",
                step="build_guide",
                status="success",
                observations_count=len(structured_output.observations) if structured_output else 0,
                rules_count=len(structured_output.candidate_rules) if structured_output else 0,
            )

            return GuideBuilderResult(
                provisional_guide=response,
                structured_output=structured_output,
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
                structured_output=None,
                success=False,
                error=str(e),
            )

    def _parse_response(self, response: str) -> Optional[GuideBuilderOutput]:
        """Parse JSON response into structured output."""
        try:
            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            return GuideBuilderOutput.model_validate(data)
        except Exception as e:
            logger.warning(
                "guide_builder_parse_warning",
                error=str(e),
                message="Could not parse structured output, using raw response",
            )
            return None

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown code blocks."""
        # Try to find JSON in code blocks
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

        # Try to find raw JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]

        return text
