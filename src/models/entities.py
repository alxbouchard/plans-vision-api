"""Database entities / domain models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    """Project lifecycle status."""
    DRAFT = "draft"
    PROCESSING = "processing"
    VALIDATED = "validated"
    FAILED = "failed"


class RuleStability(str, Enum):
    """Stability classification for a visual rule."""
    STABLE = "stable"
    PARTIAL = "partial"
    UNSTABLE = "unstable"


class Project(BaseModel):
    """A construction plan project containing multiple pages."""
    id: UUID = Field(default_factory=uuid4)
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT)
    owner_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class Page(BaseModel):
    """A single page/image within a project."""
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    order: int = Field(ge=1, description="Page order (1-indexed)")
    file_path: str = Field(description="Path to stored image file")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class RuleObservation(BaseModel):
    """Observation of a rule across pages."""
    rule_id: str
    description: str
    pages_confirmed: list[int] = Field(default_factory=list)
    pages_failed: list[int] = Field(default_factory=list)
    stability: RuleStability = RuleStability.UNSTABLE
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)


class ConfidenceReport(BaseModel):
    """Confidence report for visual guide validation."""
    total_rules: int = 0
    stable_count: int = 0
    partial_count: int = 0
    unstable_count: int = 0
    rules: list[RuleObservation] = Field(default_factory=list)
    overall_stability: float = Field(ge=0.0, le=1.0, default=0.0)
    can_generate_final: bool = False
    rejection_reason: Optional[str] = None


class VisualGuide(BaseModel):
    """Visual guide containing learned conventions for a project."""
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    provisional: Optional[str] = Field(
        default=None,
        description="Provisional guide from page 1 analysis"
    )
    stable: Optional[str] = Field(
        default=None,
        description="Final consolidated stable guide"
    )
    confidence_report: Optional[ConfidenceReport] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}
