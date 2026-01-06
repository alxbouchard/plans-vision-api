"""Extraction pipeline orchestrator."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional, Union

import json

from src.logging import get_logger
from src.storage import get_db, PageRepository, FileStorage, VisualGuideRepository, ExtractedRoomRepository, ExtractedDoorRepository
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
from src.agents.schemas import RulePayload
from .classifier import PageClassifier
from .room_extractor import RoomExtractor
from .door_extractor import DoorExtractor
from .schedule_extractor import ScheduleExtractor
from .text_block_detector import TextBlockDetector
from .spatial_room_labeler import SpatialRoomLabeler
from .tokens import get_tokens_for_page, TextToken
from .token_block_adapter import TokenBlockAdapter
from .id_generator import generate_room_id
from src.models.entities import Geometry

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


async def _load_guide_payloads(project_id: UUID) -> list[RulePayload]:
    """Load RulePayloads from the stored visual guide.

    Phase 3.3: The guide's stable_rules_json contains FinalRule objects with payloads.
    We extract all payloads to pass to the SpatialRoomLabeler.

    Returns:
        List of RulePayload objects, or empty list if no payloads found.
    """
    try:
        async with get_db() as db:
            guide_repo = VisualGuideRepository(db)
            guide = await guide_repo.get_by_project(project_id)

            if not guide or not guide.stable_rules_json:
                logger.info(
                    "phase3_3_no_guide_payloads",
                    project_id=str(project_id),
                    reason="no_stable_rules_json",
                )
                return []

            # Parse the stored GuideConsolidatorOutput JSON
            data = json.loads(guide.stable_rules_json)
            stable_rules = data.get("stable_rules", [])

            payloads = []
            for rule in stable_rules:
                payload_data = rule.get("payload")
                if payload_data:
                    try:
                        payload = RulePayload.model_validate(payload_data)
                        payloads.append(payload)
                    except Exception as e:
                        logger.warning(
                            "phase3_3_invalid_payload",
                            rule_id=rule.get("id"),
                            error=str(e),
                        )

            logger.info(
                "phase3_3_guide_payloads_loaded",
                project_id=str(project_id),
                payloads_count=len(payloads),
            )
            return payloads

    except Exception as e:
        logger.error(
            "phase3_3_load_payloads_failed",
            project_id=str(project_id),
            error=str(e),
        )
        return []


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

    # Phase 3.3: Load payloads from the stored guide
    guide_payloads = await _load_guide_payloads(project_id)

    logger.info(
        "extract_objects_started",
        project_id=str(project_id),
        policy=policy.value,
        guide_payloads_count=len(guide_payloads),
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
                    rooms = []
                    tokens_first_used = False

                    # Phase 3.5: Tokens-first room extraction
                    # If page has PDF source, use PyMuPDF tokens + guide payloads
                    pdf_path = getattr(page, 'source_pdf_path', None)
                    page_index = getattr(page, 'source_pdf_page_index', 0) or 0

                    if pdf_path and guide_payloads:
                        from pathlib import Path
                        pdf_path_obj = Path(pdf_path)

                        if pdf_path_obj.exists():
                            # Get tokens from PDF
                            tokens = await get_tokens_for_page(
                                page_id=page.id,
                                pdf_path=pdf_path_obj,
                                page_number=page_index,
                                use_vision=False,  # No vision fallback - tokens-first only
                            )

                            if tokens:
                                logger.info(
                                    "token_provider_used",
                                    page_id=str(page.id),
                                    source="pymupdf",
                                    tokens_count=len(tokens),
                                )

                                # Apply guide payloads to create room blocks
                                adapter = TokenBlockAdapter(payloads=guide_payloads)
                                blocks = adapter.create_blocks(tokens, page.id)

                                # Convert blocks to ExtractedRoom
                                rooms = _blocks_to_rooms(
                                    blocks=blocks,
                                    page_id=page.id,
                                    policy=policy,
                                    adapter_metrics=adapter.last_metrics,
                                    guide_payloads=guide_payloads,
                                )
                                tokens_first_used = True

                                logger.info(
                                    "tokens_first_rooms_extracted",
                                    page_id=str(page.id),
                                    rooms_count=len(rooms),
                                    metrics=adapter.last_metrics.to_dict() if adapter.last_metrics else {},
                                )
                            else:
                                logger.info(
                                    "token_provider_fallback",
                                    page_id=str(page.id),
                                    reason="no_tokens_from_pdf",
                                )
                        else:
                            logger.warning(
                                "token_provider_skip",
                                page_id=str(page.id),
                                reason="pdf_not_found",
                                pdf_path=pdf_path,
                            )

                    # Fallback to Vision room extractor if tokens-first didn't produce rooms
                    if not tokens_first_used:
                        logger.info(
                            "room_extractor_vision_fallback",
                            page_id=str(page.id),
                            reason="no_pdf_source" if not pdf_path else "tokens_first_failed",
                        )
                        rooms = await room_extractor.extract(page.id, image_bytes)

                    objects.extend(rooms)

                    # Extract doors (independent of rooms - can timeout without affecting rooms)
                    try:
                        doors = await door_extractor.extract(page.id, image_bytes)
                        objects.extend(doors)
                    except Exception as e:
                        logger.warning(
                            "door_extraction_timeout",
                            page_id=str(page.id),
                            error=str(e),
                        )
                        doors = []

                    _extracted_objects[page.id] = objects

                    # P0: Persist rooms and doors to database
                    await _persist_extracted_objects(page.id, rooms, doors)

                    logger.info(
                        "plan_page_extracted",
                        page_id=str(page.id),
                        room_count=len(rooms),
                        door_count=len(doors),
                        tokens_first_used=tokens_first_used,
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


async def _persist_extracted_objects(
    page_id: UUID,
    rooms: list[ExtractedRoom],
    doors: list[ExtractedDoor],
) -> None:
    """Persist extracted rooms and doors to database (P0 - Persistence).

    This ensures data survives server restarts.
    """
    try:
        async with get_db() as db:
            room_repo = ExtractedRoomRepository(db)
            door_repo = ExtractedDoorRepository(db)

            rooms_saved = await room_repo.save_rooms(page_id, rooms)
            doors_saved = await door_repo.save_doors(page_id, doors)

            logger.info(
                "objects_persisted",
                page_id=str(page_id),
                rooms_saved=rooms_saved,
                doors_saved=doors_saved,
            )
    except Exception as e:
        logger.error(
            "objects_persist_failed",
            page_id=str(page_id),
            error=str(e),
        )
        # Don't raise - extraction can continue with in-memory storage


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


def _blocks_to_rooms(
    blocks: list,
    page_id: UUID,
    policy: ExtractionPolicy,
    adapter_metrics=None,
    guide_payloads: list = None,
) -> list[ExtractedRoom]:
    """Convert SyntheticTextBlocks from TokenBlockAdapter to ExtractedRoom objects.

    Args:
        blocks: List of SyntheticTextBlock from TokenBlockAdapter
        page_id: Page identifier
        policy: Extraction policy
        adapter_metrics: Metrics from adapter for confidence adjustment
        guide_payloads: List of RulePayload from the guide

    Returns:
        List of ExtractedRoom objects
    """
    # Check if pairing payload is present in the guide
    pairing_payload_present = False
    if guide_payloads:
        for payload in guide_payloads:
            kind_value = getattr(payload.kind, 'value', str(payload.kind))
            if kind_value == "pairing":
                pairing_payload_present = True
                break

    rooms = []
    rooms_dropped_missing_number = 0

    for block in blocks:
        try:
            room_name = block.room_name_token
            room_number = block.room_number_token
            bbox = block.bbox

            # Skip blocks without room_name (shouldn't happen but defensive)
            if not room_name:
                continue

            # If pairing payload is present in guide, require room_number
            # This is guide-driven: the presence of pairing payload means
            # rooms are defined as name+number pairs in this project
            if pairing_payload_present and not room_number:
                rooms_dropped_missing_number += 1
                logger.debug(
                    "room_dropped_missing_number",
                    page_id=str(page_id),
                    room_name=room_name,
                    reason="pairing_payload_present_but_no_room_number",
                )
                continue

            # Create label
            if room_number:
                label = f"{room_name} {room_number}"
            else:
                label = room_name

            # Generate deterministic ID
            bbox_tuple = (bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3])
            object_id = generate_room_id(
                page_id=page_id,
                label=label,
                bbox=bbox_tuple,
                room_number=room_number,
            )

            # Geometry
            geometry = Geometry(
                type="bbox",
                bbox=bbox,
            )

            # Confidence: use block confidence, adjust for pairing
            confidence = block.confidence
            if room_number:
                # Paired blocks get higher confidence
                confidence = min(confidence + 0.1, 1.0)

            # Confidence level
            if confidence >= 0.8:
                confidence_level = ConfidenceLevel.HIGH
            elif confidence >= 0.5:
                confidence_level = ConfidenceLevel.MEDIUM
            else:
                confidence_level = ConfidenceLevel.LOW

            # Sources
            sources = ["tokens_first", "pymupdf"]
            if policy == ExtractionPolicy.RELAXED:
                sources.append("extraction_policy:relaxed")

            # Create room
            room = ExtractedRoom(
                id=object_id,
                page_id=page_id,
                label=label,
                geometry=geometry,
                confidence=confidence,
                confidence_level=confidence_level,
                sources=sources,
                room_number=room_number,
                room_name=room_name,
            )
            rooms.append(room)

            logger.debug(
                "tokens_first_room_created",
                page_id=str(page_id),
                object_id=object_id,
                room_name=room_name,
                room_number=room_number,
                confidence=confidence,
            )

        except Exception as e:
            logger.warning(
                "block_to_room_failed",
                page_id=str(page_id),
                error=str(e),
            )
            continue

    # Log final metrics (mandatory for Phase 3.7 validation)
    rooms_with_number = sum(1 for r in rooms if r.room_number)
    rooms_emitted_final = len(rooms)
    ratio = rooms_with_number / rooms_emitted_final if rooms_emitted_final > 0 else 0.0

    logger.info(
        "blocks_to_rooms_final",
        page_id=str(page_id),
        pairing_payload_present=pairing_payload_present,
        rooms_dropped_missing_number=rooms_dropped_missing_number,
        rooms_emitted_final=rooms_emitted_final,
        rooms_with_number=rooms_with_number,
        rooms_with_number_ratio=round(ratio, 3),
    )

    return rooms


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
