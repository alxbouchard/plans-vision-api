"""API v3 request/response schemas for Render (PDF master anchoring)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# API v3 Schema Version
# =============================================================================

SCHEMA_VERSION_V3: str = "3.1"


class BaseResponseV3(BaseModel):
    """Base class for all v3 API responses."""
    schema_version: str = Field(
        default=SCHEMA_VERSION_V3,
        description="API schema version"
    )


# =============================================================================
# PDF Upload Response
# =============================================================================

class PDFUploadResponse(BaseResponseV3):
    """Response when PDF master is uploaded."""
    project_id: UUID
    pdf_id: UUID
    page_count: int
    fingerprint: str = Field(description="SHA256 fingerprint of PDF content")
    stored_at: datetime


# =============================================================================
# Mapping Types
# =============================================================================

class AffineTransform(BaseModel):
    """Affine transform matrix for PNG to PDF coordinate conversion."""
    type: str = Field(default="affine")
    matrix: List[float] = Field(
        description="Affine matrix [a, b, c, d, e, f]",
        min_length=6,
        max_length=6
    )


class PageMapping(BaseModel):
    """Mapping data for a single page."""
    page_number: int = Field(ge=1)
    png_width: int = Field(ge=1)
    png_height: int = Field(ge=1)
    pdf_width_pt: float = Field(gt=0)
    pdf_height_pt: float = Field(gt=0)
    rotation: int = Field(description="Page rotation in degrees", ge=0, le=270)
    mediabox: List[float] = Field(min_length=4, max_length=4)
    cropbox: List[float] = Field(min_length=4, max_length=4)
    transform: AffineTransform


class MappingResponse(BaseResponseV3):
    """Response with mapping metadata."""
    project_id: UUID
    pdf_id: UUID
    fingerprint: str
    mapping_version_id: UUID
    pages: List[PageMapping]


# =============================================================================
# Mapping Job Status
# =============================================================================

class MappingJobResponse(BaseResponseV3):
    """Response when mapping job is started."""
    project_id: UUID
    pdf_id: UUID
    mapping_job_id: UUID
    status: str = "processing"


class MappingStatusResponse(BaseResponseV3):
    """Status of mapping job."""
    project_id: UUID
    pdf_id: UUID
    mapping_version_id: Optional[UUID] = None
    overall_status: str = Field(
        description="pending|running|completed|failed"
    )
    current_step: Optional[str] = Field(
        default=None,
        description="rasterize|compute_page_transform|null"
    )
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# Query Response with PDF Geometry
# =============================================================================

class GeometryPNG(BaseModel):
    """Geometry in PNG pixel coordinates."""
    type: str = "bbox"
    bbox: List[int] = Field(
        description="[x, y, width, height] in PNG pixels",
        min_length=4,
        max_length=4
    )


class GeometryPDF(BaseModel):
    """Geometry in PDF coordinates."""
    type: str = "rect"
    rect: List[float] = Field(
        description="[x1, y1, x2, y2] in PDF points",
        min_length=4,
        max_length=4
    )


class TraceInfo(BaseModel):
    """Traceability information for reproducibility."""
    pdf_id: UUID
    pdf_fingerprint: str
    mapping_version_id: UUID
    guide_version_id: Optional[UUID] = None
    extraction_run_id: Optional[UUID] = None
    index_version_id: Optional[UUID] = None


class QueryMatchV3(BaseModel):
    """A single match in query response with PDF geometry."""
    object_id: str
    type: str
    page_number: int
    label: str
    confidence: float = Field(ge=0, le=1)
    confidence_level: str
    geometry_png: GeometryPNG
    geometry_pdf: GeometryPDF
    reasons: List[str]
    trace: TraceInfo


class QueryResponseV3(BaseResponseV3):
    """Query response with PDF-anchored geometry."""
    project_id: UUID
    query: dict
    ambiguous: bool = False
    matches: List[QueryMatchV3]


# =============================================================================
# Render Requests and Responses
# =============================================================================

class RenderStyle(BaseModel):
    """Style options for rendering."""
    mode: str = Field(default="highlight", description="highlight|outline")
    include_labels: bool = True
    min_confidence_level: str = Field(
        default="medium",
        description="low|medium|high"
    )


class RenderPDFRequest(BaseModel):
    """Request to render annotated PDF."""
    schema_version: str = SCHEMA_VERSION_V3
    pdf_id: UUID
    mapping_version_id: UUID
    objects: Optional[List[str]] = Field(
        default=None,
        description="Object IDs to render, or null for all"
    )
    layers: Optional[List[str]] = Field(
        default=None,
        description="Object types to include: rooms, doors, etc."
    )
    style: RenderStyle = Field(default_factory=RenderStyle)


class RenderJobResponse(BaseResponseV3):
    """Response when render job is started."""
    project_id: UUID
    pdf_id: UUID
    render_job_id: UUID
    status: str = "processing"


class RenderTraceInfo(BaseModel):
    """Trace info for rendered output."""
    pdf_fingerprint: str
    mapping_version_id: UUID
    extraction_run_id: Optional[UUID] = None


class RenderStatusResponse(BaseResponseV3):
    """Status of render job."""
    render_job_id: UUID
    status: str
    output_pdf_url: Optional[str] = None
    trace: Optional[RenderTraceInfo] = None


# =============================================================================
# Annotations Export
# =============================================================================

class AnnotationItem(BaseModel):
    """A single annotation for export."""
    page_number: int
    type: str = "rect"
    rect: List[float] = Field(min_length=4, max_length=4)
    label: str
    object_id: str
    confidence_level: str


class RenderAnnotationsRequest(BaseModel):
    """Request to export annotations."""
    schema_version: str = SCHEMA_VERSION_V3
    pdf_id: UUID
    mapping_version_id: UUID
    objects: Optional[List[str]] = None
    format: str = Field(default="json", description="json or xfdf")


class RenderAnnotationsResponse(BaseResponseV3):
    """Annotations export response."""
    pdf_id: UUID
    format: str
    annotations: List[AnnotationItem]


# =============================================================================
# Error Response
# =============================================================================

class ErrorResponseV3(BaseResponseV3):
    """Standard error response for v3 endpoints."""
    error_code: str
    message: str
    recoverable: bool = True
