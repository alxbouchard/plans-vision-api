"""Self-Validator Agent - Analyzes validation reports to determine rule stability."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from src.config import get_settings
from src.logging import get_logger
from src.models.entities import RuleStability, RuleObservation, ConfidenceReport
from .client import VisionClient
from .prompts import get_self_validator_system, get_self_validator_prompt
from .schemas import SelfValidatorOutput, StabilityClassification

logger = get_logger(__name__)


@dataclass
class SelfValidatorResult:
    """Result from the Self-Validator agent."""
    confidence_report: ConfidenceReport
    raw_analysis: str
    structured_output: Optional[SelfValidatorOutput] = None
    success: bool = True
    error: Optional[str] = None


class SelfValidatorAgent:
    """
    Agent that analyzes validation reports to determine rule stability.

    Uses: gpt-5.2-pro with high reasoning, high verbosity
    """

    def __init__(self, client: Optional[VisionClient] = None):
        self.client = client or VisionClient()
        self.settings = get_settings()

    async def validate_stability(
        self,
        provisional_guide: str,
        validation_reports: list[tuple[int, str]],  # (page_order, report)
        project_id: str,
    ) -> SelfValidatorResult:
        """
        Analyze validation reports and determine rule stability.

        Args:
            provisional_guide: The provisional guide text
            validation_reports: List of (page_order, validation_report) tuples
            project_id: Project ID for logging

        Returns:
            SelfValidatorResult with the confidence report
        """
        logger.info(
            "self_validator_start",
            project_id=project_id,
            agent="self_validator",
            step="validate_stability",
            pages_analyzed=len(validation_reports),
        )

        try:
            # Format validation reports for the prompt
            reports_text = "\n\n".join([
                f"--- PAGE {order} VALIDATION ---\n{report}"
                for order, report in validation_reports
            ])

            prompt = get_self_validator_prompt().format(
                provisional_guide=provisional_guide,
                validation_reports=reports_text,
            )

            response = await self.client.analyze_text(
                prompt=prompt,
                model=self.settings.model_self_validator,
                reasoning_effort="high",
                verbosity="high",
                system_prompt=get_self_validator_system(),
            )

            # Parse JSON response
            structured_output = self._parse_response(response)

            # Convert to ConfidenceReport
            confidence_report = self._build_confidence_report(
                structured_output,
                len(validation_reports) + 1,  # +1 for page 1
            )

            logger.info(
                "self_validator_complete",
                project_id=project_id,
                agent="self_validator",
                step="validate_stability",
                status="success",
                stable_rules=confidence_report.stable_count,
                unstable_rules=confidence_report.unstable_count,
                can_generate=confidence_report.can_generate_final,
            )

            return SelfValidatorResult(
                confidence_report=confidence_report,
                raw_analysis=response,
                structured_output=structured_output,
                success=True,
            )

        except Exception as e:
            logger.error(
                "self_validator_error",
                project_id=project_id,
                agent="self_validator",
                step="validate_stability",
                status="error",
                error=str(e),
            )

            return SelfValidatorResult(
                confidence_report=ConfidenceReport(),
                raw_analysis="",
                success=False,
                error=str(e),
            )

    def _parse_response(self, response: str) -> Optional[SelfValidatorOutput]:
        """Parse JSON response into structured output."""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            return SelfValidatorOutput.model_validate(data)
        except Exception as e:
            logger.warning(
                "self_validator_parse_warning",
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

    def _build_confidence_report(
        self,
        structured_output: Optional[SelfValidatorOutput],
        total_pages: int,
    ) -> ConfidenceReport:
        """Build ConfidenceReport from structured output."""
        if structured_output is None:
            # Fallback: conservative empty report
            return ConfidenceReport(
                total_rules=0,
                stable_count=0,
                partial_count=0,
                unstable_count=0,
                rules=[],
                overall_stability=0.0,
                can_generate_final=False,
                rejection_reason="Failed to parse self-validator response",
            )

        # Convert structured assessments to RuleObservation objects
        rules = []
        for assessment in structured_output.rule_assessments:
            stability = self._classification_to_stability(assessment.classification)
            rules.append(RuleObservation(
                rule_id=assessment.rule_id,
                description=f"Tested on {assessment.pages_testable} pages, "
                            f"confirmed {assessment.pages_confirmed}, "
                            f"contradicted {assessment.pages_contradicted}",
                stability=stability,
                confidence_score=assessment.confidence_score,
            ))

        # Use structured output values directly
        can_generate = structured_output.can_generate_guide
        rejection_reason = structured_output.rejection_reason

        # Double-check against our threshold
        if structured_output.overall_stability_ratio < self.settings.min_stable_rules_ratio:
            can_generate = False
            if not rejection_reason:
                rejection_reason = (
                    f"Insufficient stable rules: {structured_output.stable_count}/"
                    f"{structured_output.total_rules} "
                    f"({structured_output.overall_stability_ratio:.1%}) is below the required "
                    f"{self.settings.min_stable_rules_ratio:.0%} threshold."
                )

        return ConfidenceReport(
            total_rules=structured_output.total_rules,
            stable_count=structured_output.stable_count,
            partial_count=structured_output.partial_count,
            unstable_count=structured_output.unstable_count,
            rules=rules,
            overall_stability=structured_output.overall_stability_ratio,
            can_generate_final=can_generate,
            rejection_reason=rejection_reason,
        )

    def _classification_to_stability(self, classification: StabilityClassification) -> RuleStability:
        """Convert schema classification to entity stability."""
        if classification == StabilityClassification.STABLE:
            return RuleStability.STABLE
        elif classification == StabilityClassification.PARTIAL:
            return RuleStability.PARTIAL
        else:
            return RuleStability.UNSTABLE
