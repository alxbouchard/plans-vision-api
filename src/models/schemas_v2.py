"""API v2 request/response schemas for Extraction and Query."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field

from .entities import (
    PageType,
    ConfidenceLevel,
    ObjectType,
    ExtractionStatus,
    Geometry,
    ExtractionStepStatus,
)


# =============================================================================
# API v2 Schema Version
# =============================================================================

SCHEMA_VERSION_V2: str = "2.0"


class BaseResponseV2(BaseModel):
    """Base class for all v2 API responses."""
    schema_version: str = Field(
        default=SCHEMA_VERSION_V2,
        description="API schema version"
    )


# =============================================================================
# Extraction Job Responses
# =============================================================================

class ExtractionStartResponse(BaseResponseV2):
    """Response when extraction job is started."""
    project_id: UUID
    status: str = "processing"
    job_id: UUID


class ExtractionStatusResponse(BaseResponseV2):
    """Status of extraction job."""
    project_id: UUID
    job_id: UUID
    overall_status: ExtractionStatus
    current_step: Optional[str] = None
    steps: list[ExtractionStepStatus] = Field(default_factory=list)


# =============================================================================
# Page Classification
# =============================================================================

class PageClassificationResponse(BaseResponseV2):
    """Page classification result."""
    page_id: UUID
    page_type: PageType
    confidence: float
    confidence_level: ConfidenceLevel


# =============================================================================
# Page Overlay and Objects
# =============================================================================

class ImageDimensions(BaseModel):
    """Image dimensions."""
    width: int
    height: int


class ExtractedObjectResponse(BaseModel):
    """An extracted object in the overlay."""
    id: str
    type: ObjectType
    label: Optional[str] = None
    room_number: Optional[str] = None
    room_name: Optional[str] = None
    door_type: Optional[str] = None
    geometry: Geometry
    confidence: float
    confidence_level: ConfidenceLevel
    sources: list[str] = Field(default_factory=list)


class PageOverlayResponse(BaseResponseV2):
    """Page overlay with extracted objects."""
    project_id: UUID
    page_id: UUID
    image: ImageDimensions
    page_type: PageType
    objects: list[ExtractedObjectResponse] = Field(default_factory=list)


# =============================================================================
# Project Index
# =============================================================================

class ProjectIndexResponse(BaseResponseV2):
    """Searchable project index."""
    project_id: UUID
    generated_at: datetime
    rooms_by_number: dict[str, list[str]] = Field(default_factory=dict)
    rooms_by_name: dict[str, list[str]] = Field(default_factory=dict)
    objects_by_type: dict[str, list[str]] = Field(default_factory=dict)


# =============================================================================
# Query
# =============================================================================

class QueryMatch(BaseModel):
    """A match result from a query."""
    object_id: str
    page_id: UUID
    score: float
    geometry: Geometry
    label: Optional[str] = None
    confidence_level: ConfidenceLevel
    reasons: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    """Query parameters."""
    room_number: Optional[str] = None
    room_name: Optional[str] = None
    type: Optional[ObjectType] = None


class QueryResponse(BaseResponseV2):
    """Query response with matches."""
    project_id: UUID
    query: dict[str, Any]
    matches: list[QueryMatch] = Field(default_factory=list)
    ambiguous: bool = False
    message: Optional[str] = None


# =============================================================================
# Error Response
# =============================================================================

class ErrorResponseV2(BaseResponseV2):
    """Standard v2 error response."""
    error_code: str
    message: str
    recoverable: bool = True
    details: Optional[dict] = None
