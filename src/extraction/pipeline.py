"""Extraction pipeline orchestrator."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional, Union

from src.logging import get_logger
from src.storage import get_db, PageRepository, FileStorage
from src.models.entities import (
    ExtractionStatus,
    ExtractionJob,
    ExtractionPolicy,
    PageClassification,
    PageType,
    ConfidenceLevel,
    ExtractedObject,
    ExtractedRoom,
    ExtractedDoor,
    ExtractedScheduleTable,
)
from .classifier import PageClassifier
from .room_extractor import RoomExtractor
from .door_extractor import DoorExtractor
from .schedule_extractor import ScheduleExtractor

logger = get_logger(__name__)

# In-memory storage for classifications and objects
_page_classifications: dict[UUID, PageClassification] = {}
_extracted_objects: dict[UUID, list[Union[ExtractedRoom, ExtractedDoor, ExtractedScheduleTable]]] = {}


async def run_extraction(
    project_id: UUID,
    job: ExtractionJob,
    policy: ExtractionPolicy = ExtractionPolicy.CONSERVATIVE,
) -> None:
    """
    Run the full extraction pipeline.

    Args:
        project_id: Project to extract from
        job: Extraction job for status tracking
        policy: CONSERVATIVE (stable guide) or RELAXED (provisional_only mode)

    Steps:
    1. classify_pages - Classify all pages by type
    2. extract_objects - Extract objects based on page type
    3. build_index - Build searchable index
    """
    try:
        # Step 1: Classify pages
        await _run_classify_pages(project_id, job)

        # Step 2: Extract objects (pass policy for threshold control)
        await _run_extract_objects(project_id, job, policy)

        # Step 3: Build index
        await _run_build_index(project_id, job)

        # Mark complete
        job.overall_status = ExtractionStatus.COMPLETED
        job.current_step = None
        job.updated_at = datetime.utcnow()

        logger.info(
            "extraction_completed",
            project_id=str(project_id),
            job_id=str(job.id),
        )

    except Exception as e:
        job.overall_status = ExtractionStatus.FAILED
        job.error = str(e)
        job.updated_at = datetime.utcnow()

        logger.error(
            "extraction_pipeline_failed",
            project_id=str(project_id),
            job_id=str(job.id),
            error=str(e),
        )
        raise


async def _run_classify_pages(project_id: UUID, job: ExtractionJob) -> None:
    """Step 1: Classify all pages by type and persist to database."""
    job.current_step = "classify_pages"
    _update_step_status(job, "classify_pages", ExtractionStatus.RUNNING)

    classifier = PageClassifier()
    storage = FileStorage()

    async with get_db() as db:
        page_repo = PageRepository(db)
        pages = await page_repo.list_by_project(project_id)

        for page in pages:
            try:
                # Read image bytes
                image_bytes = await storage.read_image_bytes(page.file_path)

                # Classify
                classification = await classifier.classify(page.id, image_bytes)

                # Persist classification to database (Phase 3.2 fix)
                await page_repo.update_classification(
                    page_id=page.id,
                    page_type=classification.page_type.value,
                    confidence=classification.confidence,
                    classified_at=classification.classified_at,
                )

                # Also store in memory for use in later pipeline steps
                _page_classifications[page.id] = classification

                logger.info(
                    "page_classification_persisted",
                    page_id=str(page.id),
                    page_type=classification.page_type.value,
                    confidence=classification.confidence,
                )

            except Exception as e:
                logger.error(
                    "page_classification_failed",
                    page_id=str(page.id),
                    error=str(e),
                )
                # Continue with other pages but mark as unknown
                fallback = PageClassification(
                    page_id=page.id,
                    page_type=PageType.UNKNOWN,
                    confidence=0.0,
                    confidence_level=ConfidenceLevel.LOW,
                )
                _page_classifications[page.id] = fallback
                # Persist fallback too
                await page_repo.update_classification(
                    page_id=page.id,
                    page_type=fallback.page_type.value,
                    confidence=fallback.confidence,
                    classified_at=fallback.classified_at,
                )

    _update_step_status(job, "classify_pages", ExtractionStatus.COMPLETED)


async def _run_extract_objects(
    project_id: UUID,
    job: ExtractionJob,
    policy: ExtractionPolicy,
) -> None:
    """Step 2: Extract objects based on page type."""
    job.current_step = "extract_objects"
    _update_step_status(job, "extract_objects", ExtractionStatus.RUNNING)

    storage = FileStorage()
    room_extractor = RoomExtractor(policy=policy)
    door_extractor = DoorExtractor(policy=policy)
    schedule_extractor = ScheduleExtractor()

    logger.info(
        "extract_objects_started",
        project_id=str(project_id),
        policy=policy.value,
    )

    async with get_db() as db:
        page_repo = PageRepository(db)
        pages = await page_repo.list_by_project(project_id)

        for page in pages:
            classification = _page_classifications.get(page.id)
            if not classification:
                continue

            try:
                image_bytes = await storage.read_image_bytes(page.file_path)

                if classification.page_type == PageType.PLAN:
                    # Extract rooms and doors on plan pages (Gate B, E)
                    objects = []

                    # Extract rooms
                    rooms = await room_extractor.extract(page.id, image_bytes)
                    objects.extend(rooms)

                    # Extract doors
                    doors = await door_extractor.extract(page.id, image_bytes)
                    objects.extend(doors)

                    _extracted_objects[page.id] = objects

                    logger.info(
                        "plan_page_extracted",
                        page_id=str(page.id),
                        room_count=len(rooms),
                        door_count=len(doors),
                        policy=policy.value,
                    )

                elif classification.page_type == PageType.SCHEDULE:
                    # Extract schedules on schedule pages (Gate F)
                    schedules = await schedule_extractor.extract(page.id, image_bytes)
                    _extracted_objects[page.id] = schedules

                    logger.info(
                        "schedule_page_extracted",
                        page_id=str(page.id),
                        schedule_count=len(schedules),
                    )

                else:
                    # No extraction for other page types (notes, legend, detail, unknown)
                    _extracted_objects[page.id] = []

            except Exception as e:
                logger.error(
                    "object_extraction_failed",
                    page_id=str(page.id),
                    error=str(e),
                )
                _extracted_objects[page.id] = []

    _update_step_status(job, "extract_objects", ExtractionStatus.COMPLETED)


async def _run_build_index(project_id: UUID, job: ExtractionJob) -> None:
    """Step 3: Build searchable index (Gate H - deterministic)."""
    job.current_step = "build_index"
    _update_step_status(job, "build_index", ExtractionStatus.RUNNING)

    from src.api.routes_v2.query import _project_indices

    # Build index from extracted objects
    rooms_by_number: dict[str, list[str]] = {}
    rooms_by_name: dict[str, list[str]] = {}
    objects_by_type: dict[str, list[str]] = {}

    for page_id, objects in _extracted_objects.items():
        for obj in objects:
            obj_id = obj.id
            obj_type = obj.type.value if hasattr(obj, 'type') else ""

            # Add to objects_by_type
            if obj_type:
                if obj_type not in objects_by_type:
                    objects_by_type[obj_type] = []
                objects_by_type[obj_type].append(obj_id)

            # Add rooms to room indices
            if isinstance(obj, ExtractedRoom):
                room_number = obj.room_number
                room_name = obj.room_name

                if room_number:
                    if room_number not in rooms_by_number:
                        rooms_by_number[room_number] = []
                    rooms_by_number[room_number].append(obj_id)

                if room_name:
                    if room_name not in rooms_by_name:
                        rooms_by_name[room_name] = []
                    rooms_by_name[room_name].append(obj_id)

    # Store index
    _project_indices[project_id] = {
        "generated_at": datetime.utcnow(),
        "rooms_by_number": rooms_by_number,
        "rooms_by_name": rooms_by_name,
        "objects_by_type": objects_by_type,
    }

    logger.info(
        "index_built",
        project_id=str(project_id),
        room_numbers=len(rooms_by_number),
        room_names=len(rooms_by_name),
        object_types=len(objects_by_type),
    )

    _update_step_status(job, "build_index", ExtractionStatus.COMPLETED)


def _update_step_status(
    job: ExtractionJob,
    step_name: str,
    status: ExtractionStatus,
    error: Optional[str] = None,
) -> None:
    """Update status of a specific step."""
    for step in job.steps:
        if step.name == step_name:
            step.status = status
            step.error = error
            if status == ExtractionStatus.RUNNING:
                step.started_at = datetime.utcnow()
            elif status in (ExtractionStatus.COMPLETED, ExtractionStatus.FAILED):
                step.completed_at = datetime.utcnow()
            break
    job.updated_at = datetime.utcnow()


def get_page_classification(page_id: UUID) -> Optional[PageClassification]:
    """Get stored classification for a page."""
    return _page_classifications.get(page_id)


def get_extracted_objects(page_id: UUID) -> list:
    """Get extracted objects for a page."""
    return _extracted_objects.get(page_id, [])
