"""PDF upload endpoint for tokens-first extraction."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_file_storage, get_owner_id
from src.api.middleware import increment_usage
from src.logging import analytics, get_logger
from src.models.entities import ProjectStatus
from src.models.schemas import PageResponse, ErrorResponse
from src.storage import ProjectRepository, PageRepository, FileStorage
from src.storage.file_storage import FileStorageError

logger = get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}/pdf", tags=["pdf"])


class PDFUploadResponse(BaseModel):
    """Response from PDF upload endpoint."""
    pdf_path: str = Field(..., description="Relative path to stored PDF")
    pages_created: int = Field(..., description="Number of pages extracted and created")
    pages: list[PageResponse] = Field(..., description="List of created pages")


@router.post(
    "",
    response_model=PDFUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"model": ErrorResponse, "description": "Quota exceeded"},
        404: {"model": ErrorResponse, "description": "Project not found"},
        409: {"model": ErrorResponse, "description": "Project already validated or has pages"},
        415: {"model": ErrorResponse, "description": "Invalid file type"},
    },
)
async def upload_pdf(
    request: Request,
    project_id: UUID,
    file: UploadFile = File(..., description="PDF file"),
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
    file_storage: FileStorage = Depends(get_file_storage),
) -> PDFUploadResponse:
    """
    Upload a PDF to a project and extract all pages as PNGs.

    This endpoint:
    1. Saves the PDF file
    2. Extracts each page as a PNG at 150 DPI
    3. Creates Page entries with source_pdf_path and source_pdf_page_index
    4. Enables tokens-first extraction during /analyze

    Requirements:
    - PDF format only
    - Project must be in 'draft' status
    - Project must have no existing pages (PDF upload is all-or-nothing)
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

    # Check if project already has pages (PDF upload is all-or-nothing)
    page_repo = PageRepository(session)
    current_page_count = await page_repo.count_by_project(project_id)
    if current_page_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already has pages. PDF upload must be the first upload.",
        )

    # Validate content type
    content_type = file.content_type or ""
    if content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid file type: {content_type}. Only PDF files are allowed.",
        )

    # Read PDF content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {e}",
        )

    # Save PDF and extract pages
    try:
        pdf_path, page_results = await file_storage.save_pdf_and_extract_pages(
            project_id=project_id,
            content=content,
            content_type=content_type,
        )
    except FileStorageError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            if e.error_code in ("INVALID_PDF_FORMAT",)
            else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Check page quota before creating pages
    # The check_page_quota function checks if current count >= limit
    # For PDF upload, we check if adding all pages would exceed the limit
    from src.config import get_settings
    settings = get_settings()
    if len(page_results) > settings.max_pages_per_project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"PDF has {len(page_results)} pages, exceeds maximum of {settings.max_pages_per_project}",
        )

    # Get absolute PDF path for source_pdf_path field
    pdf_abs_path = str(file_storage.base_dir / pdf_path)

    # Create Page entries with PDF source association
    created_pages: list[PageResponse] = []
    for page_result in page_results:
        page = await page_repo.create(
            project_id=project_id,
            file_path=page_result.file_path,
            image_width=page_result.metadata.width,
            image_height=page_result.metadata.height,
            image_sha256=page_result.metadata.sha256,
            byte_size=page_result.metadata.byte_size,
            source_pdf_path=pdf_abs_path,
            source_pdf_page_index=page_result.page_index,
        )

        created_pages.append(PageResponse(
            id=page.id,
            project_id=page.project_id,
            order=page.order,
            created_at=page.created_at,
        ))

        analytics.page_uploaded(str(project_id), str(page.id), page.order)

    # Increment usage counter
    increment_usage(request, pages_delta=len(created_pages))

    logger.info(
        "pdf_upload_complete",
        project_id=str(project_id),
        pdf_path=pdf_path,
        pages_created=len(created_pages),
    )

    return PDFUploadResponse(
        pdf_path=pdf_path,
        pages_created=len(created_pages),
        pages=created_pages,
    )
