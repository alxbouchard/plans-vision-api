"""
Structured output schemas for agent responses.

These schemas enforce disciplined, unambiguous outputs from each agent.
No free-form text that could hide ambiguity.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# Guide Builder Output Schema
# =============================================================================

class ConfidenceLevel(str, Enum):
    """Confidence level for an observation."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Observation(BaseModel):
    """A single visual observation from the plan."""
    id: str = Field(description="Unique observation ID (e.g., OBS_001)")
    category: str = Field(description="Category: LINE_STYLE, SYMBOL, TEXT, HATCHING, COLOR, LAYOUT")
    description: str = Field(description="What is observed - factual, no interpretation")
    location: str = Field(description="Where on the page this was observed")
    confidence: ConfidenceLevel = Field(description="Confidence in this observation")


class CandidateRule(BaseModel):
    """A candidate rule derived from observations."""
    id: str = Field(description="Unique rule ID (e.g., RULE_001)")
    description: str = Field(description="The rule statement")
    based_on: list[str] = Field(description="List of observation IDs this rule is based on")
    confidence: ConfidenceLevel = Field(description="Confidence in this rule")


class GuideBuilderOutput(BaseModel):
    """Structured output from the Guide Builder agent."""
    observations: list[Observation] = Field(description="Raw observations from the page")
    candidate_rules: list[CandidateRule] = Field(description="Rules derived from observations")
    uncertainties: list[str] = Field(description="Explicit list of things that are unclear")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Must be empty - assumptions are not allowed"
    )


# =============================================================================
# Guide Applier Output Schema
# =============================================================================

class RuleValidationStatus(str, Enum):
    """Status of a rule when validated against a page."""
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    NOT_TESTABLE = "not_testable"
    VARIATION = "variation"


class RuleValidation(BaseModel):
    """Validation result for a single rule."""
    rule_id: str = Field(description="The rule ID being validated")
    status: RuleValidationStatus = Field(description="Validation status")
    evidence: str = Field(description="Specific evidence supporting this status")
    details: Optional[str] = Field(default=None, description="Additional details if needed")


class NewObservation(BaseModel):
    """A new pattern observed that wasn't in the original guide."""
    description: str = Field(description="What was observed")
    location: str = Field(description="Where on the page")
    suggested_rule: Optional[str] = Field(default=None, description="Suggested rule if applicable")


class GuideApplierOutput(BaseModel):
    """Structured output from the Guide Applier agent."""
    page_number: int = Field(description="Page number being validated")
    rule_validations: list[RuleValidation] = Field(description="Validation for each rule")
    new_observations: list[NewObservation] = Field(
        default_factory=list,
        description="New patterns not in the guide"
    )
    overall_consistency: str = Field(description="Overall assessment: consistent, mostly_consistent, inconsistent")


# =============================================================================
# Self-Validator Output Schema
# =============================================================================

class StabilityClassification(str, Enum):
    """Stability classification for a rule - NO AMBIGUITY ALLOWED."""
    STABLE = "stable"          # 80%+ confirmed, 0 contradictions
    PARTIAL = "partial"        # 50-79% confirmed, or has variations
    UNSTABLE = "unstable"      # Any contradiction, or <50% confirmed


class RuleStabilityAssessment(BaseModel):
    """Stability assessment for a single rule."""
    rule_id: str = Field(description="The rule ID")
    classification: StabilityClassification = Field(description="MUST be one of: stable, partial, unstable")
    pages_testable: int = Field(description="Number of pages where this rule could be tested")
    pages_confirmed: int = Field(description="Number of pages where rule was confirmed")
    pages_contradicted: int = Field(description="Number of pages where rule was contradicted")
    pages_variation: int = Field(description="Number of pages with variations")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    recommendation: str = Field(description="Recommendation: include, exclude, needs_more_data")


class SelfValidatorOutput(BaseModel):
    """Structured output from the Self-Validator agent."""
    total_rules: int = Field(description="Total number of rules analyzed")
    rule_assessments: list[RuleStabilityAssessment] = Field(description="Assessment for each rule")
    stable_count: int = Field(description="Number of stable rules")
    partial_count: int = Field(description="Number of partial rules")
    unstable_count: int = Field(description="Number of unstable rules")
    overall_stability_ratio: float = Field(ge=0.0, le=1.0, description="Ratio of stable rules")
    can_generate_guide: bool = Field(description="Whether a stable guide can be generated")
    rejection_reason: Optional[str] = Field(
        default=None,
        description="If can_generate_guide is False, explain why"
    )


# =============================================================================
# Guide Consolidator Output Schema
# =============================================================================

class RuleKind(str, Enum):
    """Kind of machine-executable rule payload."""
    TOKEN_DETECTOR = "token_detector"  # Detect tokens (room_name, room_number, etc.)
    PAIRING = "pairing"                # Pair name and number tokens
    EXCLUDE = "exclude"                # Exclude global annotations


class RulePayload(BaseModel):
    """Machine-executable payload for a rule.

    This allows rules to be executed by code without interpreting text.
    The labeler reads these payloads and applies them directly.
    """
    kind: RuleKind = Field(description="Type of rule: token_detector, pairing, exclude")
    token_type: Optional[str] = Field(
        default=None,
        description="For token_detector: room_name, room_number, door_number"
    )
    detector: Optional[str] = Field(
        default=None,
        description="Detection method: regex, boxed_number, ocr_keyword"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern for detection"
    )
    min_len: Optional[int] = Field(
        default=None,
        description="Minimum token length"
    )
    must_be_boxed: Optional[bool] = Field(
        default=None,
        description="For room_number: must be inside a box/frame"
    )
    # Pairing fields
    name_token: Optional[str] = Field(
        default=None,
        description="For pairing: which token type is the name"
    )
    number_token: Optional[str] = Field(
        default=None,
        description="For pairing: which token type is the number"
    )
    relation: Optional[str] = Field(
        default=None,
        description="Spatial relation: below, above, nearest"
    )
    max_distance_px: Optional[int] = Field(
        default=None,
        description="Maximum distance in pixels for pairing"
    )
    # Examples (for observability, not execution)
    examples: Optional[list[dict]] = Field(
        default=None,
        description="Example bboxes where this rule was observed"
    )


class FinalRule(BaseModel):
    """A rule in the final stable guide."""
    id: str = Field(description="Rule ID")
    description: str = Field(description="Clear rule description")
    applies_when: str = Field(description="When/where this rule applies")
    evidence: str = Field(description="Evidence from validated pages")
    stability_score: float = Field(ge=0.0, le=1.0, description="Stability score")
    # Phase 3.3: Optional machine-executable payload
    payload: Optional[RulePayload] = Field(
        default=None,
        description="Machine-executable payload for spatial labeling"
    )


class ExcludedRule(BaseModel):
    """A rule that was excluded from the final guide."""
    id: str = Field(description="Rule ID")
    reason: str = Field(description="Why this rule was excluded")


class GuideConsolidatorOutput(BaseModel):
    """Structured output from the Guide Consolidator agent."""
    guide_generated: bool = Field(description="Whether a guide was generated")
    stable_rules: list[FinalRule] = Field(
        default_factory=list,
        description="Rules included in the final guide"
    )
    partial_observations: list[str] = Field(
        default_factory=list,
        description="Partial rules noted as observations only"
    )
    excluded_rules: list[ExcludedRule] = Field(
        default_factory=list,
        description="Rules excluded and why"
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Known limitations of this guide"
    )
    confidence_level: str = Field(description="Overall confidence: high, medium, low")
    rejection_reason: Optional[str] = Field(
        default=None,
        description="If guide_generated is False, explain why"
    )


# =============================================================================
# JSON Schema exports for prompts
# =============================================================================

def get_guide_builder_schema() -> str:
    """Get JSON schema for Guide Builder output."""
    return GuideBuilderOutput.model_json_schema()


def get_guide_applier_schema() -> str:
    """Get JSON schema for Guide Applier output."""
    return GuideApplierOutput.model_json_schema()


def get_self_validator_schema() -> str:
    """Get JSON schema for Self-Validator output."""
    return SelfValidatorOutput.model_json_schema()


def get_guide_consolidator_schema() -> str:
    """Get JSON schema for Guide Consolidator output."""
    return GuideConsolidatorOutput.model_json_schema()
