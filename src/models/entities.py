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
    PROVISIONAL_ONLY = "provisional_only"  # Stable guide rejected but provisional exists
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

    # Image metadata (Phase 2 bugfix)
    image_width: Optional[int] = Field(default=None, description="Image width in pixels")
    image_height: Optional[int] = Field(default=None, description="Image height in pixels")
    image_sha256: Optional[str] = Field(default=None, description="SHA256 hash of image bytes")
    byte_size: Optional[int] = Field(default=None, description="File size in bytes")

    # Page classification (Phase 3.2 fix - persisted instead of in-memory)
    page_type: Optional[str] = Field(default=None, description="Page type classification: plan, schedule, notes, legend, detail, unknown")
    classification_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Classification confidence score")
    classified_at: Optional[datetime] = Field(default=None, description="When the page was classified")

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
    # Phase 3.3: Structured output with payloads for extraction
    stable_rules_json: Optional[str] = Field(
        default=None,
        description="JSON of GuideConsolidatorOutput with stable_rules containing payloads"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


# =============================================================================
# Multi-tenant entities (Phase 1.5)
# =============================================================================

class Tenant(BaseModel):
    """A tenant (API user/organization) with usage tracking."""
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(description="Tenant display name")
    api_key_hash: str = Field(description="Hashed API key")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Usage tracking
    projects_count: int = Field(default=0)
    pages_this_month: int = Field(default=0)
    usage_reset_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class RateLimitEntry(BaseModel):
    """Rate limiting entry for tracking request counts."""
    tenant_id: UUID
    window_start: datetime
    request_count: int = Field(default=0)


# =============================================================================
# Phase 2 entities - Extraction and Query
# =============================================================================

class PageType(str, Enum):
    """Classification of page content type."""
    PLAN = "plan"
    SCHEDULE = "schedule"
    NOTES = "notes"
    LEGEND = "legend"
    DETAIL = "detail"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence level for extracted objects."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ObjectType(str, Enum):
    """Types of objects that can be extracted."""
    ROOM = "room"
    DOOR = "door"
    WINDOW = "window"
    STAIRS = "stairs"
    ELEVATOR = "elevator"
    SCHEDULE_TABLE = "schedule_table"
    TABLE = "table"  # Generic table for schedule extraction


class DoorType(str, Enum):
    """Types of doors that can be identified."""
    SINGLE = "single"
    DOUBLE = "double"
    SLIDING = "sliding"
    REVOLVING = "revolving"
    UNKNOWN = "unknown"


class ExtractionStatus(str, Enum):
    """Status of extraction job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionPolicy(str, Enum):
    """Extraction policy based on guide availability.

    CONSERVATIVE: Default for stable guide - reject LOW confidence extractions.
    RELAXED: For provisional_only mode - include LOW confidence but mark clearly.

    Invariants (apply to both):
    - Never invent objects not visible in the image
    - Never disambiguate arbitrarily
    - Ambiguity must be explicit (ambiguous=true)
    """
    CONSERVATIVE = "conservative"
    RELAXED = "relaxed"


class PageClassification(BaseModel):
    """Classification result for a page."""
    page_id: UUID
    page_type: PageType
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    classified_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class BoundingBox(BaseModel):
    """Bounding box geometry [x, y, width, height]."""
    x: int = Field(ge=0, description="X coordinate (top-left)")
    y: int = Field(ge=0, description="Y coordinate (top-left)")
    w: int = Field(gt=0, description="Width")
    h: int = Field(gt=0, description="Height")

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]


class Geometry(BaseModel):
    """Geometry container for extracted objects."""
    type: str = Field(default="bbox", description="Geometry type: bbox or polygon")
    bbox: list[int] = Field(
        description="Bounding box as [x, y, w, h]",
        min_length=4,
        max_length=4
    )
    polygon: Optional[list[list[int]]] = Field(
        default=None,
        description="Optional polygon points for Phase 2.1"
    )


class ExtractedObject(BaseModel):
    """Base class for extracted objects."""
    id: str = Field(description="Deterministic object ID")
    type: ObjectType
    page_id: UUID
    geometry: Geometry
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    sources: list[str] = Field(
        default_factory=list,
        description="Evidence sources: text_detected, boundary_detected, etc."
    )
    label: Optional[str] = Field(default=None, description="Detected label text")

    model_config = {"from_attributes": True}


class ExtractedRoom(ExtractedObject):
    """A room extracted from a plan page.

    Phase 3.3 additions:
    - label_bbox: bbox around the label text block (always present)
    - room_region_bbox: bbox enclosing inferred room region (nullable)
    - ambiguity: true if evidence is insufficient
    - ambiguity_reason: explanation when ambiguous
    """
    type: ObjectType = ObjectType.ROOM
    room_number: Optional[str] = Field(default=None)
    room_name: Optional[str] = Field(default=None)

    # Phase 3.3: Spatial labeling fields
    label_bbox: Optional[list[int]] = Field(
        default=None,
        description="Bounding box around the label text block [x, y, w, h]"
    )
    room_region_bbox: Optional[list[int]] = Field(
        default=None,
        description="Bounding box enclosing inferred room region, null if not inferable"
    )
    ambiguity: bool = Field(
        default=False,
        description="True if evidence is insufficient to confidently identify as room"
    )
    ambiguity_reason: Optional[str] = Field(
        default=None,
        description="Explanation when ambiguity=true"
    )


class ExtractedDoor(ExtractedObject):
    """A door extracted from a plan page."""
    type: ObjectType = ObjectType.DOOR
    door_type: str = Field(
        default="unknown",
        description="Door type: single, double, sliding, unknown"
    )


class ExtractedWindow(ExtractedObject):
    """A window extracted from a plan page."""
    type: ObjectType = ObjectType.WINDOW


class ExtractedCirculation(ExtractedObject):
    """Vertical circulation (stairs/elevator) extracted from a plan page."""
    circulation_type: str = Field(description="stairs or elevator")


class ScheduleRow(BaseModel):
    """A row in a schedule table."""
    row_index: int
    cells: list[str] = Field(default_factory=list)


class ExtractedScheduleTable(ExtractedObject):
    """A schedule table extracted from a schedule page."""
    type: ObjectType = ObjectType.SCHEDULE_TABLE
    headers: list[str] = Field(default_factory=list)
    rows: list[ScheduleRow] = Field(default_factory=list)


class ExtractionStepStatus(BaseModel):
    """Status of a single extraction step."""
    name: str
    status: ExtractionStatus
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ExtractionJob(BaseModel):
    """Extraction job tracking."""
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    overall_status: ExtractionStatus = ExtractionStatus.PENDING
    current_step: Optional[str] = None
    steps: list[ExtractionStepStatus] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectIndex(BaseModel):
    """Searchable index for a project's extracted objects."""
    project_id: UUID
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    rooms_by_number: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map room_number -> list of object IDs"
    )
    rooms_by_name: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map room_name -> list of object IDs"
    )
    objects_by_type: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map object_type -> list of object IDs"
    )

    model_config = {"from_attributes": True}
