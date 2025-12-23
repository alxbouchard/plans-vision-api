"""Page upload endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_file_storage, get_owner_id
from src.api.middleware import check_page_quota, increment_usage
from src.logging import analytics
from src.models.entities import ProjectStatus
from src.models.schemas import PageResponse, ErrorResponse
from src.storage import ProjectRepository, PageRepository, FileStorage
from src.storage.file_storage import FileStorageError

router = APIRouter(prefix="/projects/{project_id}/pages", tags=["pages"])


@router.post(
    "",
    response_model=PageResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"model": ErrorResponse, "description": "Quota exceeded"},
        404: {"model": ErrorResponse, "description": "Project not found"},
        409: {"model": ErrorResponse, "description": "Project already validated"},
        415: {"model": ErrorResponse, "description": "Invalid file type"},
    },
)
async def upload_page(
    request: Request,
    project_id: UUID,
    file: UploadFile = File(..., description="PNG image file"),
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
    file_storage: FileStorage = Depends(get_file_storage),
) -> PageResponse:
    """
    Upload a page to a project.

    Requirements:
    - PNG format only
    - Project must be in 'draft' status
    - Pages are immutable after upload
    """
    # Validate project exists and belongs to owner
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id, owner_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check project status - cannot add pages to validated projects
    if project.status == ProjectStatus.VALIDATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add pages to a validated project",
        )

    if project.status == ProjectStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add pages while project is processing",
        )

    # Check page quota
    page_repo = PageRepository(session)
    current_page_count = await page_repo.count_by_project(project_id)
    check_page_quota(request, current_page_count)

    # Validate content type
    content_type = file.content_type or ""
    if content_type != "image/png":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid file type: {content_type}. Only PNG images are allowed.",
        )

    # Read and save file
    try:
        content = await file.read()
        file_path, metadata = await file_storage.save_image(
            project_id=project_id,
            content=content,
            content_type=content_type,
        )
    except FileStorageError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e),
        )

    # Create page record with image metadata
    page = await page_repo.create(
        project_id=project_id,
        file_path=file_path,
        image_width=metadata.width,
        image_height=metadata.height,
        image_sha256=metadata.sha256,
        byte_size=metadata.byte_size,
    )

    # Increment usage counter
    increment_usage(request, pages_delta=1)

    analytics.page_uploaded(str(project_id), str(page.id), page.order)

    return PageResponse(
        id=page.id,
        project_id=page.project_id,
        order=page.order,
        created_at=page.created_at,
    )


@router.get(
    "",
    response_model=list[PageResponse],
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
)
async def list_pages(
    project_id: UUID,
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[PageResponse]:
    """
    List all pages in a project.
    """
    # Validate project exists and belongs to owner
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id, owner_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    page_repo = PageRepository(session)
    pages = await page_repo.list_by_project(project_id)

    return [
        PageResponse(
            id=page.id,
            project_id=page.project_id,
            order=page.order,
            created_at=page.created_at,
        )
        for page in pages
    ]
