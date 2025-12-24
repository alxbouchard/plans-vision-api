"""Analysis and guide generation endpoints."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_file_storage, get_owner_id
from src.logging import analytics, get_logger
from src.models.entities import ProjectStatus
from src.models.schemas import (
    AnalysisStartResponse,
    ErrorResponse,
    PipelineStatusResponse,
    UsageStatsSchema,
    VisualGuideResponse,
)
from src.pipeline import PipelineOrchestrator, PipelineError
from src.storage import ProjectRepository, VisualGuideRepository, FileStorage
from src.agents.client import get_current_usage

logger = get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["analysis"])


async def run_pipeline_background(
    project_id: UUID,
    owner_id: UUID,
    session: AsyncSession,
    file_storage: FileStorage,
) -> None:
    """Background task to run the analysis pipeline."""
    orchestrator = PipelineOrchestrator(session, file_storage)

    try:
        result = await orchestrator.run(project_id, owner_id)

        analytics.guide_build_completed(
            str(project_id),
            result.has_stable_guide,
            result.pages_processed,
        )

    except PipelineError as e:
        analytics.guide_build_failed(
            str(project_id),
            e.error_code,
            str(e),
        )
        logger.error(
            "pipeline_background_error",
            project_id=str(project_id),
            error_code=e.error_code,
            error=str(e),
        )

    except Exception as e:
        analytics.guide_build_failed(
            str(project_id),
            "UNEXPECTED_ERROR",
            str(e),
        )
        logger.error(
            "pipeline_background_unexpected_error",
            project_id=str(project_id),
            error=str(e),
        )


@router.post(
    "/analyze",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
        409: {"model": ErrorResponse, "description": "Invalid project state"},
        422: {"model": ErrorResponse, "description": "Insufficient pages"},
    },
)
async def start_analysis(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
    file_storage: FileStorage = Depends(get_file_storage),
) -> AnalysisStartResponse:
    """
    Start the analysis pipeline for a project.

    This triggers the multi-agent pipeline:
    1. Guide Builder analyzes page 1
    2. Guide Applier validates against pages 2-N
    3. Self-Validator assesses stability
    4. Guide Consolidator produces final guide (or rejects)

    The analysis runs in the background. Use GET /projects/{id}/status to monitor.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id, owner_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status == ProjectStatus.VALIDATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already validated",
        )

    if project.status == ProjectStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis already in progress",
        )

    # Check page count (at least 1 required)
    page_count = await project_repo.get_page_count(project_id)
    if page_count < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 1 page required",
        )

    # Update status and start background task
    await project_repo.update_status(project_id, ProjectStatus.PROCESSING)

    analytics.guide_build_started(str(project_id))

    # Note: In production, this should use a proper task queue (Celery, etc.)
    # For simplicity, using FastAPI background tasks
    background_tasks.add_task(
        run_pipeline_background,
        project_id,
        owner_id,
        session,
        file_storage,
    )

    return AnalysisStartResponse(
        project_id=project_id,
        message="Analysis started",
        pages_to_process=page_count,
    )


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
)
async def get_analysis_status(
    project_id: UUID,
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
) -> PipelineStatusResponse:
    """
    Get the current status of the analysis pipeline.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id, owner_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    page_count = await project_repo.get_page_count(project_id)

    # Determine current step based on status and guide state
    current_step = None
    error_message = None
    has_provisional = False
    has_stable = False
    rejection_reason = None

    guide_repo = VisualGuideRepository(session)
    guide = await guide_repo.get_by_project(project_id)

    if guide:
        has_provisional = guide.provisional is not None
        has_stable = guide.stable is not None
        if guide.confidence_report and guide.confidence_report.rejection_reason:
            rejection_reason = guide.confidence_report.rejection_reason

    if project.status == ProjectStatus.PROCESSING:
        if guide is None or guide.provisional is None:
            current_step = "guide_builder"
        elif guide.confidence_report is None:
            current_step = "validation"
        else:
            current_step = "consolidation"

    elif project.status == ProjectStatus.FAILED:
        if rejection_reason:
            error_message = rejection_reason

    # Get current usage stats
    usage_stats = None
    if project.status == ProjectStatus.PROCESSING:
        usage = get_current_usage()
        usage_stats = UsageStatsSchema(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cost_usd=round(usage.cost_usd, 4),
            requests=usage.requests,
        )

    return PipelineStatusResponse(
        project_id=project_id,
        status=project.status,
        current_step=current_step,
        pages_processed=page_count if project.status != ProjectStatus.PROCESSING else 0,
        total_pages=page_count,
        has_provisional=has_provisional,
        has_stable=has_stable,
        rejection_reason=rejection_reason,
        error_message=error_message,
        usage=usage_stats,
    )


@router.get(
    "/guide",
    response_model=VisualGuideResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Project or guide not found"},
    },
)
async def get_visual_guide(
    project_id: UUID,
    owner_id: UUID = Depends(get_owner_id),
    session: AsyncSession = Depends(get_db_session),
) -> VisualGuideResponse:
    """
    Get the visual guide for a project.

    Returns both provisional and stable guides if available,
    along with the confidence report.
    """
    # Validate project exists
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id, owner_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Get guide
    guide_repo = VisualGuideRepository(session)
    guide = await guide_repo.get_by_project(project_id)

    if guide is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No visual guide found for this project",
        )

    return VisualGuideResponse(
        project_id=guide.project_id,
        has_provisional=guide.provisional is not None,
        has_stable=guide.stable is not None,
        provisional=guide.provisional,
        stable=guide.stable,
        confidence_report=guide.confidence_report,
        created_at=guide.created_at,
        updated_at=guide.updated_at,
    )
