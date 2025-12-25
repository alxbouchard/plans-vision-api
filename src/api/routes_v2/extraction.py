"""V2 extraction endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.logging import get_logger
from src.storage import get_db, ProjectRepository, PageRepository, VisualGuideRepository, FileStorage
from src.api.dependencies import get_db_session, get_file_storage
from src.models.entities import ExtractionStatus, ExtractionJob, ExtractionStepStatus, ExtractionPolicy
from src.models.schemas_v2 import (
    SCHEMA_VERSION_V2,
    ExtractionStartResponse,
    ExtractionStatusResponse,
    PageOverlayResponse,
    ErrorResponseV2,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/v2/projects", tags=["extraction"])

# In-memory storage for extraction jobs (will be replaced with DB in production)
_extraction_jobs: dict[UUID, ExtractionJob] = {}


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


@router.post("/{project_id}/extract", response_model=ExtractionStartResponse)
async def start_extraction(
    project_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Start extraction pipeline for a project.

    Requires a stable or provisional guide to exist.
    Returns 202 with job_id for tracking.

    Errors:
    - 404 PROJECT_NOT_FOUND
    - 409 GUIDE_REQUIRED
    - 409 EXTRACT_ALREADY_RUNNING
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    async with get_db() as db:
        project_repo = ProjectRepository(db)
        guide_repo = VisualGuideRepository(db)

        # Check project exists (with tenant check if tenant_id present)
        if tenant_id:
            project = await project_repo.get_by_id(project_id, tenant_id)
        else:
            project = await project_repo.get_by_id_no_tenant(project_id)
        if not project:
            return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

        # Check guide exists (stable or provisional)
        guide = await guide_repo.get_by_project(project_id)
        if not guide or (not guide.provisional and not guide.stable):
            return _error_response(
                409,
                "GUIDE_REQUIRED",
                "A visual guide is required before extraction. Run analysis first.",
                recoverable=True,
            )

        # Determine extraction policy based on guide state
        # RELAXED: provisional exists but no stable (provisional_only mode)
        # CONSERVATIVE: stable guide exists (default)
        has_provisional = guide.provisional is not None
        has_stable = guide.stable is not None
        extraction_policy = ExtractionPolicy.RELAXED if (has_provisional and not has_stable) else ExtractionPolicy.CONSERVATIVE

        # Determine guide source for logging
        guide_source = "stable" if has_stable else ("provisional" if has_provisional else "none")

        # Get feature flag status
        from src.config import get_settings
        settings = get_settings()

        # LOG 1: Phase 3.3 status at extraction start (mandatory structured log)
        logger.info(
            "phase3_3_extraction_start",
            project_id=str(project_id),
            phase3_3_enabled=settings.enable_phase3_3_spatial_labeling,
            extraction_policy=extraction_policy.value,
            guide_source=guide_source,
        )

        logger.info(
            "extraction_policy_determined",
            project_id=str(project_id),
            policy=extraction_policy.value,
            has_provisional=has_provisional,
            has_stable=has_stable,
        )

        # Check if extraction already running
        existing_job = _extraction_jobs.get(project_id)
        if existing_job and existing_job.overall_status == ExtractionStatus.RUNNING:
            return _error_response(
                409,
                "EXTRACT_ALREADY_RUNNING",
                "Extraction is already in progress for this project",
                recoverable=True,
            )

        # Create extraction job
        job = ExtractionJob(
            project_id=project_id,
            overall_status=ExtractionStatus.RUNNING,
            current_step="classify_pages",
            steps=[
                ExtractionStepStatus(name="classify_pages", status=ExtractionStatus.PENDING),
                ExtractionStepStatus(name="extract_objects", status=ExtractionStatus.PENDING),
                ExtractionStepStatus(name="build_index", status=ExtractionStatus.PENDING),
            ],
        )
        _extraction_jobs[project_id] = job

        # Start extraction in background with policy
        background_tasks.add_task(_run_extraction_pipeline, project_id, job.id, extraction_policy)

        logger.info(
            "extraction_started",
            project_id=str(project_id),
            job_id=str(job.id),
        )

        return JSONResponse(
            status_code=202,
            content=ExtractionStartResponse(
                project_id=project_id,
                job_id=job.id,
            ).model_dump(mode="json"),
        )


@router.get("/{project_id}/extract/status", response_model=ExtractionStatusResponse)
async def get_extraction_status(
    project_id: UUID,
    request: Request,
):
    """
    Get extraction job status.

    Returns current step and per-step status.
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

    # Get job status
    job = _extraction_jobs.get(project_id)
    if not job:
        # No extraction job exists - return pending status
        return ExtractionStatusResponse(
            project_id=project_id,
            job_id=UUID("00000000-0000-0000-0000-000000000000"),
            overall_status=ExtractionStatus.PENDING,
            current_step=None,
            steps=[],
        )

    return ExtractionStatusResponse(
        project_id=project_id,
        job_id=job.id,
        overall_status=job.overall_status,
        current_step=job.current_step,
        steps=job.steps,
    )


@router.get("/{project_id}/pages/{page_id}/overlay", response_model=PageOverlayResponse)
async def get_page_overlay(
    project_id: UUID,
    page_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    file_storage: FileStorage = Depends(get_file_storage),
):
    """
    Get extracted objects overlay for a specific page.

    Returns page type, dimensions, and list of extracted objects.
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    project_repo = ProjectRepository(session)
    page_repo = PageRepository(session)

    # Check project exists (with tenant check if tenant_id present)
    if tenant_id:
        project = await project_repo.get_by_id(project_id, tenant_id)
    else:
        project = await project_repo.get_by_id_no_tenant(project_id)
    if not project:
        return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

    # Check page exists
    page = await page_repo.get_by_id(page_id, project_id)
    if not page:
        return _error_response(404, "PAGE_NOT_FOUND", "Page not found")

    # Backfill metadata if missing (for pages created before Phase 2 bugfix)
    if page.image_width is None or page.image_height is None:
        try:
            metadata = await file_storage.compute_image_metadata(page.file_path)
            await page_repo.update_metadata(
                page_id=page.id,
                image_width=metadata.width,
                image_height=metadata.height,
                image_sha256=metadata.sha256,
                byte_size=metadata.byte_size,
            )
            # Update local page object with backfilled values
            page.image_width = metadata.width
            page.image_height = metadata.height
            page.image_sha256 = metadata.sha256
            page.byte_size = metadata.byte_size
            logger.info(
                "metadata_backfilled",
                page_id=str(page_id),
                width=metadata.width,
                height=metadata.height,
            )
        except Exception as e:
            logger.error(
                "metadata_backfill_failed",
                page_id=str(page_id),
                error=str(e),
            )
            # Continue with fallback dimensions
            pass

    # Return overlay with real dimensions (or fallback if backfill failed)
    from src.models.entities import PageType, ConfidenceLevel as ConfLevelEnum
    from src.models.schemas_v2 import ImageDimensions, ExtractedObjectResponse, ObjectType, Geometry
    from src.extraction.pipeline import get_extracted_objects

    width = page.image_width if page.image_width else 0
    height = page.image_height if page.image_height else 0

    # Get page_type from database (single source of truth - Phase 3.2 fix)
    # page.page_type is persisted during extraction classify_pages step
    if page.page_type:
        try:
            page_type = PageType(page.page_type)
        except ValueError:
            page_type = PageType.UNKNOWN
    else:
        # Not yet classified - extraction hasn't run
        page_type = PageType.UNKNOWN

    # Get extracted objects from in-memory storage
    # NOTE: Objects are stored in-memory only and will be lost on server restart.
    # This is acceptable for Phase 2 as extraction can be re-run.
    # Future: Persist objects to database if they need to survive restarts.
    extracted = get_extracted_objects(page_id)
    objects = []
    for obj in extracted:
        # Determine object type
        obj_type = ObjectType.UNKNOWN
        if hasattr(obj, 'type'):
            try:
                obj_type = ObjectType(obj.type.value)
            except ValueError:
                obj_type = ObjectType.UNKNOWN

        # Build geometry - handle both direct bbox and geometry.bbox
        if hasattr(obj, 'geometry') and obj.geometry:
            geometry = Geometry(type=obj.geometry.type, bbox=obj.geometry.bbox)
        elif hasattr(obj, 'bbox'):
            geometry = Geometry(type="bbox", bbox=obj.bbox)
        else:
            geometry = Geometry(type="bbox", bbox=[0, 0, 0, 0])

        # Get confidence level
        conf_level = obj.confidence_level if hasattr(obj, 'confidence_level') else ConfLevelEnum.LOW

        objects.append(ExtractedObjectResponse(
            id=obj.id,
            type=obj_type,
            label=getattr(obj, 'label', None),
            room_number=getattr(obj, 'room_number', None),
            room_name=getattr(obj, 'room_name', None),
            door_type=getattr(obj, 'door_type', None),
            geometry=geometry,
            confidence=obj.confidence,
            confidence_level=conf_level,
        ))

    return PageOverlayResponse(
        project_id=project_id,
        page_id=page_id,
        image=ImageDimensions(width=width, height=height),
        page_type=page_type,
        objects=objects,
    )


async def _run_extraction_pipeline(project_id: UUID, job_id: UUID, policy: ExtractionPolicy) -> None:
    """Run the extraction pipeline in background."""
    from src.extraction.pipeline import run_extraction

    job = _extraction_jobs.get(project_id)
    if not job:
        return

    try:
        await run_extraction(project_id, job, policy)
    except Exception as e:
        logger.error(
            "extraction_failed",
            project_id=str(project_id),
            job_id=str(job_id),
            error=str(e),
        )
        job.overall_status = ExtractionStatus.FAILED
        job.error = str(e)
