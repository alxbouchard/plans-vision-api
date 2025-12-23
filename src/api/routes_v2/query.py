"""V2 query endpoints.

Per TEST_GATES_PHASE2.md:
- Gate C: Query room number works - GET /v2/projects/{id}/query?room_number=203 returns
  - status 200
  - matches length >= 1
  - ambiguous false if unique
  - bbox present in match

- Gate D: Ambiguous query is explicit
  - A query expected to match multiple results
  - Must return ambiguous true and multiple matches
  - Must not pick one arbitrarily

Per PHASE2_DECISIONS.md:
- Identifier Reuse Across Object Types:
  - Do not merge or delete objects solely because their extracted numeric text matches
  - Treat identifiers as scoped by object type and visual context
  - If a query matches multiple objects, return ambiguous rather than choosing arbitrarily
"""

from uuid import UUID
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from src.logging import get_logger
from src.storage import get_db, ProjectRepository
from src.models.entities import ObjectType, ExtractedRoom, ExtractedDoor
from src.models.schemas_v2 import (
    QueryResponse,
    QueryMatch,
    ProjectIndexResponse,
    ErrorResponseV2,
)
from src.extraction.pipeline import _extracted_objects

logger = get_logger(__name__)

router = APIRouter(prefix="/v2/projects", tags=["query"])

# In-memory storage for project indices (will be replaced with DB)
_project_indices: dict[UUID, dict] = {}


def _error_response(status_code: int, error_code: str, message: str, recoverable: bool = True) -> JSONResponse:
    """Create a v2 error response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponseV2(
            error_code=error_code,
            message=message,
            recoverable=recoverable,
        ).model_dump(),
    )


@router.get("/{project_id}/index", response_model=ProjectIndexResponse)
async def get_project_index(
    project_id: UUID,
    request: Request,
):
    """
    Get the project's searchable index.

    Returns maps for rooms_by_number, rooms_by_name, and objects_by_type.
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    async with get_db() as db:
        project_repo = ProjectRepository(db)

        # Check project exists (with tenant check if tenant_id present)
        if tenant_id:
            project = await project_repo.get_by_id(project_id, tenant_id)
        else:
            project = await project_repo.get_by_id_no_tenant(project_id)
        if not project:
            return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

    # Get index
    index = _project_indices.get(project_id)
    if not index:
        # Return empty index
        return ProjectIndexResponse(
            project_id=project_id,
            generated_at=datetime.utcnow(),
            rooms_by_number={},
            rooms_by_name={},
            objects_by_type={},
        )

    return ProjectIndexResponse(
        project_id=project_id,
        generated_at=index.get("generated_at"),
        rooms_by_number=index.get("rooms_by_number", {}),
        rooms_by_name=index.get("rooms_by_name", {}),
        objects_by_type=index.get("objects_by_type", {}),
    )


@router.get("/{project_id}/query", response_model=QueryResponse)
async def query_project(
    project_id: UUID,
    request: Request,
    room_number: Optional[str] = Query(None, description="Search by room number"),
    room_name: Optional[str] = Query(None, description="Search by room name"),
    type: Optional[str] = Query(None, description="Search by object type"),
):
    """
    Query extracted objects in a project.

    Supports queries by:
    - room_number: Find rooms by number (e.g., "203")
    - room_name: Find rooms by name (e.g., "CLASSE")
    - type: Find objects by type (e.g., "door", "room")

    Returns matches with geometry, confidence, and ambiguity flag.

    Per PHASE2_DECISIONS.md:
    - If a query matches multiple objects, return ambiguous=true
    - Do not pick one arbitrarily
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    async with get_db() as db:
        project_repo = ProjectRepository(db)

        # Check project exists (with tenant check if tenant_id present)
        if tenant_id:
            project = await project_repo.get_by_id(project_id, tenant_id)
        else:
            project = await project_repo.get_by_id_no_tenant(project_id)
        if not project:
            return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

    # Build query dict
    query_params = {}
    if room_number:
        query_params["room_number"] = room_number
    if room_name:
        query_params["room_name"] = room_name
    if type:
        query_params["type"] = type

    if not query_params:
        return _error_response(
            400,
            "QUERY_EMPTY",
            "At least one query parameter is required",
        )

    # Perform query
    matches = _execute_query(project_id, room_number, room_name, type)

    # Determine ambiguity (Gate D)
    # Per PHASE2_DECISIONS.md: If query matches multiple, return ambiguous=true
    ambiguous = len(matches) > 1
    message = "Multiple candidates found" if ambiguous else None

    logger.info(
        "query_executed",
        project_id=str(project_id),
        query=query_params,
        match_count=len(matches),
        ambiguous=ambiguous,
    )

    return QueryResponse(
        project_id=project_id,
        query=query_params,
        matches=matches,
        ambiguous=ambiguous,
        message=message,
    )


def _execute_query(
    project_id: UUID,
    room_number: Optional[str],
    room_name: Optional[str],
    object_type: Optional[str],
) -> list[QueryMatch]:
    """
    Execute query against extracted objects.

    Per PHASE2_DECISIONS.md:
    - Identifiers are scoped by object type and visual context
    - Do not merge objects solely because numeric text matches
    """
    matches = []

    # Get project index
    index = _project_indices.get(project_id)
    if not index:
        return matches

    # Find matching object IDs from index
    matching_ids = set()
    match_reasons: dict[str, list[str]] = {}

    if room_number:
        room_ids = index.get("rooms_by_number", {}).get(room_number, [])
        for obj_id in room_ids:
            matching_ids.add(obj_id)
            match_reasons.setdefault(obj_id, []).append("room_number_match")

    if room_name:
        room_ids = index.get("rooms_by_name", {}).get(room_name, [])
        for obj_id in room_ids:
            matching_ids.add(obj_id)
            match_reasons.setdefault(obj_id, []).append("room_name_match")

    if object_type:
        obj_ids = index.get("objects_by_type", {}).get(object_type, [])
        for obj_id in obj_ids:
            matching_ids.add(obj_id)
            match_reasons.setdefault(obj_id, []).append("type_match")

    # Build matches from extracted objects
    for page_id, objects in _extracted_objects.items():
        for obj in objects:
            if obj.id in matching_ids:
                # Build reasons
                reasons = match_reasons.get(obj.id, [])
                if len(matching_ids) == 1:
                    reasons.append("unique_match")

                match = QueryMatch(
                    object_id=obj.id,
                    page_id=page_id,
                    score=obj.confidence,
                    geometry=obj.geometry,
                    label=obj.label,
                    confidence_level=obj.confidence_level,
                    reasons=reasons,
                )
                matches.append(match)

    return matches
