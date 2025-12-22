"""Guide Consolidator Agent - Produces final stable guide from validated conventions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from src.config import get_settings
from src.logging import get_logger
from src.models.entities import ConfidenceReport
from .client import VisionClient
from .prompts import get_guide_consolidator_system, get_guide_consolidator_prompt
from .schemas import GuideConsolidatorOutput

logger = get_logger(__name__)


@dataclass
class ConsolidatorResult:
    """Result from the Guide Consolidator agent."""
    stable_guide: Optional[str]
    rejection_message: Optional[str]
    structured_output: Optional[GuideConsolidatorOutput] = None
    success: bool = True
    error: Optional[str] = None


class GuideConsolidatorAgent:
    """
    Agent that produces a final stable guide from validated conventions.

    Uses: gpt-5.2 with medium reasoning, high verbosity

    CRITICAL: Will refuse to generate if too few rules are stable.
    """

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()
        self.settings = get_settings()

    async def consolidate_guide(
        self,
        provisional_guide: str,
        confidence_report: ConfidenceReport,
        raw_stability_analysis: str,
        project_id: str,
    ) -> ConsolidatorResult:
        """
        Produce a final stable guide or refuse if stability is insufficient.

        Args:
            provisional_guide: The provisional guide text
            confidence_report: The parsed confidence report
            raw_stability_analysis: The raw stability analysis text
            project_id: Project ID for logging

        Returns:
            ConsolidatorResult with stable guide or rejection message
        """
        logger.info(
            "guide_consolidator_start",
            project_id=project_id,
            agent="guide_consolidator",
            step="consolidate_guide",
            can_generate=confidence_report.can_generate_final,
        )

        # Check if we should even attempt consolidation
        if not confidence_report.can_generate_final:
            logger.info(
                "guide_consolidator_rejected",
                project_id=project_id,
                agent="guide_consolidator",
                step="consolidate_guide",
                status="rejected",
                reason=confidence_report.rejection_reason,
            )

            return ConsolidatorResult(
                stable_guide=None,
                rejection_message=confidence_report.rejection_reason,
                success=True,  # This is a valid outcome, not an error
            )

        try:
            # Format the stability report for the prompt
            stability_summary = self._format_stability_report(confidence_report)

            prompt = get_guide_consolidator_prompt().format(
                provisional_guide=provisional_guide,
                stability_report=f"{stability_summary}\n\nDETAILED ANALYSIS:\n{raw_stability_analysis}",
                min_stable_ratio=int(self.settings.min_stable_rules_ratio * 100),
            )

            response = await self.client.analyze_text(
                prompt=prompt,
                model=self.settings.model_guide_consolidator,
                reasoning_effort="medium",
                verbosity="high",
                system_prompt=get_guide_consolidator_system(),
            )

            # Parse JSON response
            structured_output = self._parse_response(response)

            # Check if guide was generated
            if structured_output is None:
                # Fallback: check text for rejection
                if self._is_rejection_response(response):
                    return ConsolidatorResult(
                        stable_guide=None,
                        rejection_message=response,
                        structured_output=None,
                        success=True,
                    )
                # Otherwise treat as success
                return ConsolidatorResult(
                    stable_guide=response,
                    rejection_message=None,
                    structured_output=None,
                    success=True,
                )

            # Use structured output
            if not structured_output.guide_generated:
                logger.info(
                    "guide_consolidator_model_rejected",
                    project_id=project_id,
                    agent="guide_consolidator",
                    step="consolidate_guide",
                    status="model_rejected",
                    reason=structured_output.rejection_reason,
                )

                return ConsolidatorResult(
                    stable_guide=None,
                    rejection_message=structured_output.rejection_reason,
                    structured_output=structured_output,
                    success=True,
                )

            # Format the stable guide from structured output
            stable_guide = self._format_stable_guide(structured_output)

            logger.info(
                "guide_consolidator_complete",
                project_id=project_id,
                agent="guide_consolidator",
                step="consolidate_guide",
                status="success",
                stable_rules_count=len(structured_output.stable_rules),
                confidence=structured_output.confidence_level,
            )

            return ConsolidatorResult(
                stable_guide=stable_guide,
                rejection_message=None,
                structured_output=structured_output,
                success=True,
            )

        except Exception as e:
            logger.error(
                "guide_consolidator_error",
                project_id=project_id,
                agent="guide_consolidator",
                step="consolidate_guide",
                status="error",
                error=str(e),
            )

            return ConsolidatorResult(
                stable_guide=None,
                rejection_message=None,
                success=False,
                error=str(e),
            )

    def _format_stability_report(self, report: ConfidenceReport) -> str:
        """Format the confidence report as readable text."""
        lines = [
            "STABILITY SUMMARY",
            "=" * 40,
            f"Total Rules Analyzed: {report.total_rules}",
            f"Stable Rules: {report.stable_count}",
            f"Partial Rules: {report.partial_count}",
            f"Unstable Rules: {report.unstable_count}",
            f"Overall Stability: {report.overall_stability:.1%}",
            f"Can Generate Final Guide: {report.can_generate_final}",
            "",
            "RULE BREAKDOWN:",
        ]

        for rule in report.rules:
            lines.append(
                f"  - {rule.rule_id}: {rule.stability.value} "
                f"(confidence: {rule.confidence_score:.1%})"
            )

        if report.rejection_reason:
            lines.extend([
                "",
                "REJECTION REASON:",
                f"  {report.rejection_reason}",
            ])

        return "\n".join(lines)

    def _parse_response(self, response: str) -> Optional[GuideConsolidatorOutput]:
        """Parse JSON response into structured output."""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            return GuideConsolidatorOutput.model_validate(data)
        except Exception as e:
            logger.warning(
                "guide_consolidator_parse_warning",
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

    def _format_stable_guide(self, output: GuideConsolidatorOutput) -> str:
        """Format the structured output into a readable stable guide."""
        lines = [
            "# VALIDATED VISUAL GUIDE",
            f"Confidence Level: {output.confidence_level.upper()}",
            "",
            "## STABLE RULES",
            "",
        ]

        for rule in output.stable_rules:
            lines.extend([
                f"### {rule.id}",
                f"**Description:** {rule.description}",
                f"**Applies when:** {rule.applies_when}",
                f"**Evidence:** {rule.evidence}",
                f"**Stability Score:** {rule.stability_score:.0%}",
                "",
            ])

        if output.partial_observations:
            lines.extend([
                "## PARTIAL OBSERVATIONS",
                "(Noted but not validated enough to be rules)",
                "",
            ])
            for obs in output.partial_observations:
                lines.append(f"- {obs}")
            lines.append("")

        if output.excluded_rules:
            lines.extend([
                "## EXCLUDED RULES",
                "",
            ])
            for excluded in output.excluded_rules:
                lines.append(f"- **{excluded.id}**: {excluded.reason}")
            lines.append("")

        if output.limitations:
            lines.extend([
                "## LIMITATIONS",
                "",
            ])
            for limitation in output.limitations:
                lines.append(f"- {limitation}")
            lines.append("")

        return "\n".join(lines)

    def _is_rejection_response(self, response: str) -> bool:
        """Check if the model's response is a rejection rather than a guide."""
        rejection_indicators = [
            "cannot produce",
            "cannot generate",
            "unable to produce",
            "insufficient stable rules",
            "not enough stable",
            "refuse to produce",
            "refusing to generate",
        ]
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in rejection_indicators)
