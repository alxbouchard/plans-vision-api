"""Self-Validator Agent - Analyzes validation reports to determine rule stability."""

import json
import re
from dataclasses import dataclass
from typing import Optional

from src.config import get_settings
from src.logging import get_logger
from src.models.entities import RuleStability, RuleObservation, ConfidenceReport
from .client import VisionClient
from .prompts import SELF_VALIDATOR_SYSTEM, SELF_VALIDATOR_PROMPT

logger = get_logger(__name__)


@dataclass
class SelfValidatorResult:
    """Result from the Self-Validator agent."""
    confidence_report: ConfidenceReport
    raw_analysis: str
    success: bool
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

            prompt = SELF_VALIDATOR_PROMPT.format(
                provisional_guide=provisional_guide,
                validation_reports=reports_text,
            )

            response = await self.client.analyze_text(
                prompt=prompt,
                model=self.settings.model_self_validator,
                reasoning_effort="high",
                verbosity="high",
                system_prompt=SELF_VALIDATOR_SYSTEM,
            )

            # Parse the response to extract structured data
            confidence_report = self._parse_stability_response(
                response,
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
            )

            return SelfValidatorResult(
                confidence_report=confidence_report,
                raw_analysis=response,
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

    def _parse_stability_response(
        self,
        response: str,
        total_pages: int,
    ) -> ConfidenceReport:
        """
        Parse the model's stability analysis into a structured report.

        This is a heuristic parser - the model output is semi-structured.
        """
        rules = []
        stable_count = 0
        partial_count = 0
        unstable_count = 0

        # Look for rule patterns in the response
        # Expected format includes STABLE, PARTIAL, UNSTABLE markers
        lines = response.split('\n')

        current_rule_id = None
        current_description = ""
        current_stability = None

        for line in lines:
            line_lower = line.lower().strip()

            # Detect stability markers
            if 'stable' in line_lower and 'unstable' not in line_lower:
                if 'partial' in line_lower:
                    current_stability = RuleStability.PARTIAL
                else:
                    current_stability = RuleStability.STABLE
            elif 'unstable' in line_lower:
                current_stability = RuleStability.UNSTABLE

            # Try to extract rule IDs (patterns like "Rule 1:", "RULE_001:", etc.)
            rule_match = re.search(r'rule[_\s]*(\d+|[a-z]+)', line_lower)
            if rule_match:
                # Save previous rule if exists
                if current_rule_id and current_stability:
                    score = self._stability_to_score(current_stability)
                    rules.append(RuleObservation(
                        rule_id=current_rule_id,
                        description=current_description.strip(),
                        stability=current_stability,
                        confidence_score=score,
                    ))
                    if current_stability == RuleStability.STABLE:
                        stable_count += 1
                    elif current_stability == RuleStability.PARTIAL:
                        partial_count += 1
                    else:
                        unstable_count += 1

                current_rule_id = f"RULE_{rule_match.group(1).upper()}"
                current_description = line
                current_stability = None

            elif current_rule_id:
                current_description += " " + line

        # Save last rule
        if current_rule_id and current_stability:
            score = self._stability_to_score(current_stability)
            rules.append(RuleObservation(
                rule_id=current_rule_id,
                description=current_description.strip(),
                stability=current_stability,
                confidence_score=score,
            ))
            if current_stability == RuleStability.STABLE:
                stable_count += 1
            elif current_stability == RuleStability.PARTIAL:
                partial_count += 1
            else:
                unstable_count += 1

        # Calculate overall stability
        total_rules = len(rules) if rules else 1
        overall_stability = stable_count / total_rules if total_rules > 0 else 0.0

        # Determine if we can generate final guide
        can_generate = overall_stability >= self.settings.min_stable_rules_ratio
        rejection_reason = None
        if not can_generate:
            rejection_reason = (
                f"Insufficient stable rules: {stable_count}/{total_rules} "
                f"({overall_stability:.1%}) is below the required "
                f"{self.settings.min_stable_rules_ratio:.0%} threshold."
            )

        return ConfidenceReport(
            total_rules=total_rules,
            stable_count=stable_count,
            partial_count=partial_count,
            unstable_count=unstable_count,
            rules=rules,
            overall_stability=overall_stability,
            can_generate_final=can_generate,
            rejection_reason=rejection_reason,
        )

    def _stability_to_score(self, stability: RuleStability) -> float:
        """Convert stability enum to a confidence score."""
        if stability == RuleStability.STABLE:
            return 0.9
        elif stability == RuleStability.PARTIAL:
            return 0.6
        else:
            return 0.2
