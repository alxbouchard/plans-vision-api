"""V2 object access endpoints.

Provides access to extracted objects (rooms, doors) after extraction is complete.

Endpoints:
- GET /v2/projects/{id}/rooms - List all extracted rooms
- GET /v2/projects/{id}/doors - List all extracted doors
- GET /v2/projects/{id}/objects - List all extracted objects (rooms + doors + schedules)
"""

from uuid import UUID
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.logging import get_logger
from src.storage import get_db, ProjectRepository, PageRepository, ExtractedRoomRepository, ExtractedDoorRepository
from src.models.entities import ExtractedRoom, ExtractedDoor, ExtractedScheduleTable
from src.models.schemas_v2 import ErrorResponseV2

logger = get_logger(__name__)

router = APIRouter(prefix="/v2/projects", tags=["objects"])


# Response schemas
class RoomResponse(BaseModel):
    """Single room in the response."""
    id: str
    page_id: str
    room_name: Optional[str] = None
    room_number: Optional[str] = None
    label: str
    bbox: list[float] = Field(description="[x, y, width, height]")
    confidence: float
    confidence_level: str
    sources: list[str]


class RoomsListResponse(BaseModel):
    """Response for GET /rooms endpoint."""
    schema_version: str = "2.0"
    project_id: str
    rooms: list[RoomResponse]
    total_count: int


class DoorResponse(BaseModel):
    """Single door in the response."""
    id: str
    page_id: str
    door_number: Optional[str] = None
    label: str
    bbox: list[float] = Field(description="[x, y, width, height]")
    confidence: float
    confidence_level: str
    sources: list[str]


class DoorsListResponse(BaseModel):
    """Response for GET /doors endpoint."""
    schema_version: str = "2.0"
    project_id: str
    doors: list[DoorResponse]
    total_count: int


class ObjectResponse(BaseModel):
    """Generic object in the response."""
    id: str
    page_id: str
    type: str
    label: str
    bbox: list[float]
    confidence: float
    confidence_level: str
    sources: list[str]
    # Optional fields depending on type
    room_name: Optional[str] = None
    room_number: Optional[str] = None
    door_number: Optional[str] = None


class ObjectsListResponse(BaseModel):
    """Response for GET /objects endpoint."""
    schema_version: str = "2.0"
    project_id: str
    objects: list[ObjectResponse]
    total_count: int
    rooms_count: int
    doors_count: int
    schedules_count: int


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Create a v2 error response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponseV2(
            error_code=error_code,
            message=message,
            recoverable=True,
        ).model_dump(),
    )


@router.get("/{project_id}/rooms", response_model=RoomsListResponse)
async def get_rooms(
    project_id: UUID,
    request: Request,
    page_id: Optional[UUID] = Query(None, description="Filter by page ID"),
):
    """
    Get all extracted rooms for a project.

    Returns rooms with:
    - id, page_id, room_name, room_number, label
    - bbox, confidence, confidence_level, sources

    Use after /extract is completed to access extraction results.
    Rooms are read from database (persisted after extraction).
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    async with get_db() as db:
        # Validate project exists
        project_repo = ProjectRepository(db)
        if tenant_id:
            project = await project_repo.get_by_id(project_id, tenant_id)
        else:
            project = await project_repo.get_by_id_no_tenant(project_id)
        if not project:
            return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

        # Read rooms from database (P0 - Persistence)
        room_repo = ExtractedRoomRepository(db)
        room_dicts = await room_repo.list_by_project(project_id)

    # Filter by page_id if requested
    if page_id:
        room_dicts = [r for r in room_dicts if r["page_id"] == str(page_id)]

    # Convert to response objects
    rooms = [
        RoomResponse(
            id=r["id"],
            page_id=r["page_id"],
            room_name=r["room_name"],
            room_number=r["room_number"],
            label=r["label"],
            bbox=r["bbox"],
            confidence=r["confidence"],
            confidence_level=r["confidence_level"],
            sources=r["sources"],
        )
        for r in room_dicts
    ]

    logger.info(
        "rooms_listed",
        project_id=str(project_id),
        rooms_count=len(rooms),
        page_filter=str(page_id) if page_id else None,
        source="database",
    )

    return RoomsListResponse(
        project_id=str(project_id),
        rooms=rooms,
        total_count=len(rooms),
    )


@router.get("/{project_id}/doors", response_model=DoorsListResponse)
async def get_doors(
    project_id: UUID,
    request: Request,
    page_id: Optional[UUID] = Query(None, description="Filter by page ID"),
):
    """
    Get all extracted doors for a project.

    Returns doors with:
    - id, page_id, door_number, label
    - bbox, confidence, confidence_level, sources

    Use after /extract is completed to access extraction results.
    Doors are read from database (persisted after extraction).
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    async with get_db() as db:
        # Validate project exists
        project_repo = ProjectRepository(db)
        if tenant_id:
            project = await project_repo.get_by_id(project_id, tenant_id)
        else:
            project = await project_repo.get_by_id_no_tenant(project_id)
        if not project:
            return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

        # Read doors from database (P0 - Persistence)
        door_repo = ExtractedDoorRepository(db)
        door_dicts = await door_repo.list_by_project(project_id)

    # Filter by page_id if requested
    if page_id:
        door_dicts = [d for d in door_dicts if d["page_id"] == str(page_id)]

    # Convert to response objects
    doors = [
        DoorResponse(
            id=d["id"],
            page_id=d["page_id"],
            door_number=d["door_number"],
            label=d["label"],
            bbox=d["bbox"],
            confidence=d["confidence"],
            confidence_level=d["confidence_level"],
            sources=d["sources"],
        )
        for d in door_dicts
    ]

    logger.info(
        "doors_listed",
        project_id=str(project_id),
        doors_count=len(doors),
        page_filter=str(page_id) if page_id else None,
        source="database",
    )

    return DoorsListResponse(
        project_id=str(project_id),
        doors=doors,
        total_count=len(doors),
    )


@router.get("/{project_id}/objects", response_model=ObjectsListResponse)
async def get_objects(
    project_id: UUID,
    request: Request,
    page_id: Optional[UUID] = Query(None, description="Filter by page ID"),
    type: Optional[str] = Query(None, description="Filter by object type: room, door, schedule"),
):
    """
    Get all extracted objects for a project.

    Returns all objects (rooms, doors, schedules) with full metadata.

    Use after /extract is completed to access extraction results.
    Objects are read from database (persisted after extraction).
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    async with get_db() as db:
        # Validate project exists
        project_repo = ProjectRepository(db)
        if tenant_id:
            project = await project_repo.get_by_id(project_id, tenant_id)
        else:
            project = await project_repo.get_by_id_no_tenant(project_id)
        if not project:
            return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

        # Read rooms and doors from database (P0 - Persistence)
        room_repo = ExtractedRoomRepository(db)
        door_repo = ExtractedDoorRepository(db)

        room_dicts = await room_repo.list_by_project(project_id)
        door_dicts = await door_repo.list_by_project(project_id)

    # Filter by page_id if requested
    if page_id:
        room_dicts = [r for r in room_dicts if r["page_id"] == str(page_id)]
        door_dicts = [d for d in door_dicts if d["page_id"] == str(page_id)]

    objects = []
    rooms_count = 0
    doors_count = 0
    schedules_count = 0

    # Add rooms
    if type is None or type == "room":
        for r in room_dicts:
            objects.append(ObjectResponse(
                id=r["id"],
                page_id=r["page_id"],
                type="room",
                label=r["label"],
                bbox=r["bbox"],
                confidence=r["confidence"],
                confidence_level=r["confidence_level"],
                sources=r["sources"],
                room_name=r["room_name"],
                room_number=r["room_number"],
                door_number=None,
            ))
            rooms_count += 1

    # Add doors
    if type is None or type == "door":
        for d in door_dicts:
            objects.append(ObjectResponse(
                id=d["id"],
                page_id=d["page_id"],
                type="door",
                label=d["label"],
                bbox=d["bbox"],
                confidence=d["confidence"],
                confidence_level=d["confidence_level"],
                sources=d["sources"],
                room_name=None,
                room_number=None,
                door_number=d["door_number"],
            ))
            doors_count += 1

    # Schedules not yet persisted - count stays 0

    logger.info(
        "objects_listed",
        project_id=str(project_id),
        total_count=len(objects),
        rooms_count=rooms_count,
        doors_count=doors_count,
        schedules_count=schedules_count,
        page_filter=str(page_id) if page_id else None,
        type_filter=type,
        source="database",
    )

    return ObjectsListResponse(
        project_id=str(project_id),
        objects=objects,
        total_count=len(objects),
        rooms_count=rooms_count,
        doors_count=doors_count,
        schedules_count=schedules_count,
    )
