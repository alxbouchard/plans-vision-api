"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .entities import ProjectStatus, ConfidenceReport


class ProjectCreate(BaseModel):
    """Request to create a new project."""
    owner_id: UUID = Field(description="Owner/tenant ID")


class ProjectResponse(BaseModel):
    """Project response."""
    id: UUID
    status: ProjectStatus
    owner_id: UUID
    created_at: datetime
    page_count: int = 0

    model_config = {"from_attributes": True}


class PageResponse(BaseModel):
    """Page response."""
    id: UUID
    project_id: UUID
    order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VisualGuideResponse(BaseModel):
    """Visual guide response."""
    project_id: UUID
    has_provisional: bool
    has_stable: bool
    provisional: Optional[str] = None
    stable: Optional[str] = None
    confidence_report: Optional[ConfidenceReport] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineStatusResponse(BaseModel):
    """Status of the processing pipeline."""
    project_id: UUID
    status: ProjectStatus
    current_step: Optional[str] = None
    pages_processed: int = 0
    total_pages: int = 0
    error_message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    error_code: str
    message: str
    details: Optional[dict] = None


class AnalysisStartResponse(BaseModel):
    """Response when starting analysis."""
    project_id: UUID
    message: str
    pages_to_process: int
