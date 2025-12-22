"""Project management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_owner_id
from src.logging import analytics
from src.models.entities import ProjectStatus
from src.models.schemas import ProjectCreate, ProjectResponse, ErrorResponse
from src.storage import ProjectRepository

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def create_project(
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """
    Create a new project.

    A project starts in 'draft' status and can accept page uploads.
    """
    repo = ProjectRepository(session)
    project = await repo.create(owner_id)

    analytics.project_created(str(project.id), str(owner_id))

    return ProjectResponse(
        id=project.id,
        status=project.status,
        owner_id=project.owner_id,
        created_at=project.created_at,
        page_count=0,
    )


@router.get(
    "",
    response_model=list[ProjectResponse],
)
async def list_projects(
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectResponse]:
    """
    List all projects for the current owner.
    """
    repo = ProjectRepository(session)
    projects = await repo.list_by_owner(owner_id)

    result = []
    for project in projects:
        page_count = await repo.get_page_count(project.id)
        result.append(ProjectResponse(
            id=project.id,
            status=project.status,
            owner_id=project.owner_id,
            created_at=project.created_at,
            page_count=page_count,
        ))

    return result


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
)
async def get_project(
    project_id: UUID,
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """
    Get a project by ID.
    """
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id, owner_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    page_count = await repo.get_page_count(project.id)

    return ProjectResponse(
        id=project.id,
        status=project.status,
        owner_id=project.owner_id,
        created_at=project.created_at,
        page_count=page_count,
    )
