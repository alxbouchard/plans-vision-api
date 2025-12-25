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
from src.config import Settings, get_settings
from .classifier import PageClassifier
from .room_extractor import RoomExtractor
from .door_extractor import DoorExtractor
from .schedule_extractor import ScheduleExtractor
from .text_block_detector import TextBlockDetector
from .spatial_room_labeler import SpatialRoomLabeler

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
                logger.warning(
                    "page_no_classification",
                    page_id=str(page.id),
                )
                continue

            # Log page type for debugging Phase 3.3 flow
            logger.info(
                "extract_objects_page",
                page_id=str(page.id),
                page_type=classification.page_type.value,
                confidence=classification.confidence,
            )

            try:
                image_bytes = await storage.read_image_bytes(page.file_path)

                if classification.page_type == PageType.PLAN:
                    # Extract rooms and doors on plan pages (Gate B, E)
                    objects = []
                    settings = get_settings()

                    # Extract doors FIRST (needed for Phase 3.3 disambiguation)
                    doors = await door_extractor.extract(page.id, image_bytes)
                    objects.extend(doors)

                    # Extract rooms (legacy extractor)
                    rooms = await room_extractor.extract(page.id, image_bytes)
                    objects.extend(rooms)

                    # Phase 3.3: Spatial room labeling (if enabled)
                    # Runs after doors so we can use door context for disambiguation
                    spatial_rooms = await _run_phase3_3_spatial_labeling(
                        page_id=page.id,
                        image_bytes=image_bytes,
                        doors=doors,
                        settings=settings,
                        policy=policy,
                    )
                    if spatial_rooms:
                        objects.extend(spatial_rooms)

                    _extracted_objects[page.id] = objects

                    # Count rooms from both extractors
                    total_rooms = len(rooms) + len(spatial_rooms)

                    logger.info(
                        "plan_page_extracted",
                        page_id=str(page.id),
                        room_count=total_rooms,
                        door_count=len(doors),
                        spatial_rooms=len(spatial_rooms),
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


# =============================================================================
# Phase 3.3: Spatial Room Labeling Hook
# =============================================================================

async def _run_phase3_3_spatial_labeling(
    page_id: UUID,
    image_bytes: bytes,
    doors: list[ExtractedDoor],
    settings: Settings,
    policy: ExtractionPolicy = ExtractionPolicy.CONSERVATIVE,
    payloads: Optional[list] = None,
) -> list[ExtractedRoom]:
    """Phase 3.3 hook: Run spatial room labeling if feature flag is enabled.

    Per WORK_QUEUE_PHASE3_3.md Ticket 2:
    - When flag is False: return empty list, zero model calls
    - When flag is True: run text block detection and spatial labeling

    Args:
        page_id: The page ID
        image_bytes: The image bytes
        doors: Extracted doors for disambiguation (Ticket 9)
        settings: Settings instance (to check feature flag)
        policy: Extraction policy
        payloads: Machine-executable rule payloads from guide (Phase 3.3)

    Returns:
        List of ExtractedRoom objects from spatial labeling
    """
    # Check feature flag
    if not settings.enable_phase3_3_spatial_labeling:
        logger.debug(
            "phase3_3_skipped_flag_off",
            page_id=str(page_id),
        )
        return []

    # LOG 2: Mandatory log BEFORE calling detector (so it appears even if detector fails)
    logger.info(
        "phase3_3_text_block_detector_called",
        page_id=str(page_id),
        phase3_3_text_block_detector_called=True,
    )

    try:
        # Step 1: Detect text blocks (Ticket 5 will add vision implementation)
        detector = TextBlockDetector(use_vision=True)
        text_blocks = await detector.detect(page_id=page_id, image_bytes=image_bytes)

        # LOG 2b: Result after successful detection
        logger.info(
            "phase3_3_text_blocks_detected",
            page_id=str(page_id),
            blocks_found=len(text_blocks),
        )

        if not text_blocks:
            return []

        # Step 2: Convert doors to door symbol format for labeler
        door_symbols = []
        for door in doors:
            if hasattr(door, 'bbox') and door.bbox:
                door_symbols.append(door)

        # Step 3: Run spatial room labeler (Ticket 7)
        labeler = SpatialRoomLabeler(policy=policy, payloads=payloads or [])
        rooms = labeler.extract_rooms(
            page_id=page_id,
            text_blocks=text_blocks,
            door_symbols=door_symbols,
        )

        # Count ambiguous rooms
        ambiguous_count = sum(1 for r in rooms if r.ambiguity)
        candidates_before_filter = len(rooms)

        # Filter out ambiguous rooms in conservative mode
        if policy == ExtractionPolicy.CONSERVATIVE:
            rooms = [r for r in rooms if not r.ambiguity]

        # LOG 3: Mandatory log when SpatialRoomLabeler is called
        logger.info(
            "phase3_3_spatial_room_labeler_called",
            page_id=str(page_id),
            phase3_3_spatial_room_labeler_called=True,
            candidates=candidates_before_filter,
            rooms_emitted=len(rooms),
            ambiguous_count=ambiguous_count,
        )

        return rooms

    except Exception as e:
        logger.error(
            "phase3_3_labeling_failed",
            page_id=str(page_id),
            error=str(e),
        )
        # Per FEATURE doc: if detector fails, pipeline continues with existing extractor
        return []
