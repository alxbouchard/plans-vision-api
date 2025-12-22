"""API request/response schemas with complete OpenAPI documentation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .entities import ProjectStatus, ConfidenceReport, RuleStability, RuleObservation


# =============================================================================
# Enums for OpenAPI documentation
# =============================================================================

class PipelineStep(str, Enum):
    """Current step in the analysis pipeline."""
    GUIDE_BUILDER = "guide_builder"
    VALIDATION = "validation"
    CONSOLIDATION = "consolidation"


# =============================================================================
# Request Schemas
# =============================================================================

class ProjectCreate(BaseModel):
    """Request to create a new project."""
    owner_id: UUID = Field(description="Owner/tenant ID")


# =============================================================================
# Response Schemas
# =============================================================================

class ProjectResponse(BaseModel):
    """
    Project response.

    Example:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "draft",
            "owner_id": "123e4567-e89b-12d3-a456-426614174000",
            "created_at": "2024-01-15T10:30:00Z",
            "page_count": 3
        }
    """
    id: UUID = Field(description="Unique project identifier")
    status: ProjectStatus = Field(
        description="Project lifecycle status: draft, processing, validated, or failed"
    )
    owner_id: UUID = Field(description="Owner/tenant ID for isolation")
    created_at: datetime = Field(description="Project creation timestamp")
    page_count: int = Field(default=0, description="Number of pages uploaded")

    model_config = {"from_attributes": True}


class PageResponse(BaseModel):
    """
    Page upload response.

    Example:
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "project_id": "550e8400-e29b-41d4-a716-446655440000",
            "order": 1,
            "created_at": "2024-01-15T10:31:00Z"
        }
    """
    id: UUID = Field(description="Unique page identifier")
    project_id: UUID = Field(description="Parent project ID")
    order: int = Field(description="Page order (1-indexed, auto-incremented)")
    created_at: datetime = Field(description="Upload timestamp")

    model_config = {"from_attributes": True}


# =============================================================================
# Structured Guide Response Schemas
# =============================================================================

class StableRuleSchema(BaseModel):
    """
    A validated stable rule in the final guide.

    Example:
        {
            "id": "RULE_001",
            "description": "Structural walls use thick black lines",
            "applies_when": "Drawing structural elements",
            "evidence": "Confirmed on pages 1, 2, 3, 4",
            "stability_score": 0.95
        }
    """
    id: str = Field(description="Rule identifier (e.g., RULE_001)")
    description: str = Field(description="Clear rule description")
    applies_when: str = Field(description="When/where this rule applies")
    evidence: str = Field(description="Evidence from validated pages")
    stability_score: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score 0.0-1.0"
    )


class ExcludedRuleSchema(BaseModel):
    """
    A rule excluded from the final guide.

    Example:
        {
            "id": "RULE_003",
            "reason": "Contradicted on page 3: doors shown with different symbol"
        }
    """
    id: str = Field(description="Rule identifier")
    reason: str = Field(description="Why this rule was excluded")


class RuleObservationSchema(BaseModel):
    """
    Observation of a rule's validation status across pages.

    Example:
        {
            "rule_id": "RULE_001",
            "description": "Tested on 3 pages, confirmed 3, contradicted 0",
            "stability": "stable",
            "confidence_score": 0.95
        }
    """
    rule_id: str = Field(description="Rule identifier")
    description: str = Field(description="Validation summary")
    stability: RuleStability = Field(
        description="Classification: stable (80%+, 0 contradictions), "
                    "partial (50-79% or variations), "
                    "unstable (any contradiction or <50%)"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score 0.0-1.0"
    )


class ConfidenceReportSchema(BaseModel):
    """
    Detailed confidence report for guide validation.

    Example:
        {
            "total_rules": 5,
            "stable_count": 3,
            "partial_count": 1,
            "unstable_count": 1,
            "rules": [...],
            "overall_stability": 0.6,
            "can_generate_final": true,
            "rejection_reason": null
        }
    """
    total_rules: int = Field(description="Total number of rules analyzed")
    stable_count: int = Field(description="Rules classified as stable")
    partial_count: int = Field(description="Rules classified as partial")
    unstable_count: int = Field(description="Rules classified as unstable")
    rules: list[RuleObservationSchema] = Field(
        default_factory=list,
        description="Detailed per-rule observations"
    )
    overall_stability: float = Field(
        ge=0.0, le=1.0,
        description="Ratio of stable rules (stable_count / total_rules)"
    )
    can_generate_final: bool = Field(
        description="Whether a stable guide can be generated (requires >= 60% stable)"
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="If can_generate_final is false, explains why"
    )


class VisualGuideResponse(BaseModel):
    """
    Visual guide response containing provisional and/or stable guide.

    For single-page projects (Option B):
    - has_provisional: true
    - has_stable: false
    - provisional: contains candidate rules from page 1
    - stable: null
    - confidence_report.rejection_reason: explains single-page limitation

    For multi-page validated projects:
    - has_stable: true if guide generated
    - stable: formatted guide with only stable rules
    - confidence_report: full validation details

    Example (single page):
        {
            "project_id": "...",
            "has_provisional": true,
            "has_stable": false,
            "provisional": "{observations: [...], candidate_rules: [...]}",
            "stable": null,
            "confidence_report": {
                "rejection_reason": "Only 1 page - cross-validation not possible",
                "stable_count": 0,
                "can_generate_final": false
            }
        }

    Example (validated):
        {
            "project_id": "...",
            "has_provisional": true,
            "has_stable": true,
            "provisional": "...",
            "stable": "# VALIDATED VISUAL GUIDE\\n...",
            "confidence_report": {
                "stable_count": 4,
                "unstable_count": 1,
                "overall_stability": 0.8,
                "can_generate_final": true
            }
        }
    """
    project_id: UUID = Field(description="Project identifier")
    has_provisional: bool = Field(
        description="Whether a provisional guide exists (from page 1 analysis)"
    )
    has_stable: bool = Field(
        description="Whether a stable validated guide was generated"
    )
    provisional: Optional[str] = Field(
        default=None,
        description="Provisional guide JSON from Guide Builder agent"
    )
    stable: Optional[str] = Field(
        default=None,
        description="Final validated guide (markdown format) with only stable rules"
    )
    confidence_report: Optional[ConfidenceReport] = Field(
        default=None,
        description="Detailed validation report with per-rule stability"
    )
    created_at: datetime = Field(description="Guide creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    model_config = {"from_attributes": True}


class UsageStatsSchema(BaseModel):
    """
    Token usage and cost statistics.

    Example:
        {
            "input_tokens": 15420,
            "output_tokens": 3200,
            "total_tokens": 18620,
            "cost_usd": 0.0523,
            "requests": 4
        }
    """
    input_tokens: int = Field(default=0, description="Total input tokens used")
    output_tokens: int = Field(default=0, description="Total output tokens used")
    total_tokens: int = Field(default=0, description="Total tokens (input + output)")
    cost_usd: float = Field(default=0.0, description="Estimated cost in USD")
    requests: int = Field(default=0, description="Number of API requests made")


class PipelineStatusResponse(BaseModel):
    """
    Status of the analysis pipeline.

    Example (processing):
        {
            "project_id": "...",
            "status": "processing",
            "current_step": "validation",
            "pages_processed": 2,
            "total_pages": 5,
            "error_message": null,
            "usage": {"input_tokens": 10000, "cost_usd": 0.035}
        }

    Example (failed with rejection):
        {
            "project_id": "...",
            "status": "failed",
            "current_step": null,
            "pages_processed": 5,
            "total_pages": 5,
            "error_message": "Insufficient stable rules: 1/5 (20%) below 60% threshold"
        }
    """
    project_id: UUID = Field(description="Project identifier")
    status: ProjectStatus = Field(
        description="Current status: draft, processing, validated, or failed"
    )
    current_step: Optional[PipelineStep] = Field(
        default=None,
        description="Current pipeline step if processing"
    )
    pages_processed: int = Field(
        default=0,
        description="Number of pages processed so far"
    )
    total_pages: int = Field(
        default=0,
        description="Total pages in project"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error or rejection message if failed"
    )
    usage: Optional[UsageStatsSchema] = Field(
        default=None,
        description="Token usage and cost statistics for current pipeline run"
    )


class ErrorResponse(BaseModel):
    """
    Standard error response.

    Example:
        {
            "error_code": "PROJECT_NOT_FOUND",
            "message": "Project not found",
            "details": {"project_id": "..."}
        }
    """
    error_code: str = Field(
        description="Machine-readable error code",
        examples=["PROJECT_NOT_FOUND", "INSUFFICIENT_PAGES", "ALREADY_VALIDATED"]
    )
    message: str = Field(description="Human-readable error message")
    details: Optional[dict] = Field(
        default=None,
        description="Additional error context"
    )


class AnalysisStartResponse(BaseModel):
    """
    Response when analysis is started.

    Example:
        {
            "project_id": "550e8400-e29b-41d4-a716-446655440000",
            "message": "Analysis started",
            "pages_to_process": 5
        }
    """
    project_id: UUID = Field(description="Project being analyzed")
    message: str = Field(description="Status message")
    pages_to_process: int = Field(description="Number of pages to analyze")


# =============================================================================
# Agent Output Schemas (for documentation/transparency)
# =============================================================================

class ObservationSchema(BaseModel):
    """
    A visual observation from the Guide Builder agent.

    Example:
        {
            "id": "OBS_001",
            "category": "LINE_STYLE",
            "description": "Thick black lines (2px) observed on structural walls",
            "location": "All exterior walls on page 1",
            "confidence": "high"
        }
    """
    id: str = Field(description="Observation ID (e.g., OBS_001)")
    category: str = Field(
        description="Category: LINE_STYLE, SYMBOL, TEXT, HATCHING, COLOR, LAYOUT"
    )
    description: str = Field(description="Factual observation without interpretation")
    location: str = Field(description="Where on the page this was observed")
    confidence: str = Field(description="Confidence level: high, medium, low")


class CandidateRuleSchema(BaseModel):
    """
    A candidate rule from the Guide Builder agent.

    Example:
        {
            "id": "RULE_001",
            "description": "Structural walls are drawn with thick black lines (2px)",
            "based_on": ["OBS_001", "OBS_002"],
            "confidence": "high"
        }
    """
    id: str = Field(description="Rule ID (e.g., RULE_001)")
    description: str = Field(description="Rule statement")
    based_on: list[str] = Field(description="Observation IDs this rule is based on")
    confidence: str = Field(description="Confidence level: high, medium, low")


class GuideBuilderOutputSchema(BaseModel):
    """
    Structured output from the Guide Builder agent (page 1 analysis).

    CRITICAL: assumptions array MUST be empty. No guessing allowed.

    Example:
        {
            "observations": [...],
            "candidate_rules": [...],
            "uncertainties": ["Cannot determine if dashed lines mean proposed vs existing"],
            "assumptions": []
        }
    """
    observations: list[ObservationSchema] = Field(
        description="Raw visual observations from page 1"
    )
    candidate_rules: list[CandidateRuleSchema] = Field(
        description="Rules derived from observations"
    )
    uncertainties: list[str] = Field(
        description="Explicit list of unclear elements"
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="MUST be empty - assumptions are not allowed"
    )


class RuleValidationSchema(BaseModel):
    """
    Validation result for a single rule from Guide Applier.

    Example:
        {
            "rule_id": "RULE_001",
            "status": "confirmed",
            "evidence": "Page 2 shows same thick black lines on structural walls",
            "details": null
        }
    """
    rule_id: str = Field(description="Rule being validated")
    status: str = Field(
        description="Status: confirmed, contradicted, not_testable, variation"
    )
    evidence: str = Field(description="Specific evidence from this page")
    details: Optional[str] = Field(default=None, description="Additional details")
