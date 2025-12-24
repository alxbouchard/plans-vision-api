"""Pipeline orchestrator for the multi-agent analysis flow."""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.logging import get_logger
from src.models.entities import ProjectStatus, ConfidenceReport
from src.storage import (
    ProjectRepository,
    PageRepository,
    VisualGuideRepository,
    FileStorage,
)
from src.agents import (
    GuideBuilderAgent,
    GuideApplierAgent,
    SelfValidatorAgent,
    GuideConsolidatorAgent,
)

logger = get_logger(__name__)


class PipelineError(Exception):
    """Pipeline execution error."""

    def __init__(self, message: str, error_code: str = "PIPELINE_ERROR"):
        super().__init__(message)
        self.error_code = error_code


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    success: bool
    has_stable_guide: bool
    stable_guide: Optional[str] = None
    provisional_guide: Optional[str] = None
    rejection_message: Optional[str] = None
    error: Optional[str] = None
    pages_processed: int = 0
    is_provisional_only: bool = False


class PipelineOrchestrator:
    """
    Orchestrates the multi-agent pipeline for visual guide generation.

    Pipeline flow:
    1. Guide Builder (page 1) -> provisional guide
    2. Guide Applier (pages 2-N) -> validation reports
    3. Self-Validator -> stability analysis
    4. Guide Consolidator -> stable guide OR rejection
    """

    def __init__(
        self,
        session: AsyncSession,
        file_storage: Optional[FileStorage] = None,
    ):
        self.session = session
        self.file_storage = file_storage or FileStorage()

        # Repositories
        self.projects = ProjectRepository(session)
        self.pages = PageRepository(session)
        self.guides = VisualGuideRepository(session)

        # Agents
        self.guide_builder = GuideBuilderAgent()
        self.guide_applier = GuideApplierAgent()
        self.self_validator = SelfValidatorAgent()
        self.guide_consolidator = GuideConsolidatorAgent()

    async def run(self, project_id: UUID, owner_id: UUID) -> PipelineResult:
        """
        Run the full pipeline for a project.

        Args:
            project_id: The project to process
            owner_id: Owner ID for tenant validation

        Returns:
            PipelineResult with outcome
        """
        project_id_str = str(project_id)

        logger.info(
            "pipeline_start",
            project_id=project_id_str,
            step="start",
        )

        try:
            # Validate project exists and belongs to owner
            project = await self.projects.get_by_id(project_id, owner_id)
            if project is None:
                raise PipelineError(
                    "Project not found",
                    error_code="PROJECT_NOT_FOUND"
                )

            # Check project status
            if project.status == ProjectStatus.VALIDATED:
                raise PipelineError(
                    "Project already validated",
                    error_code="ALREADY_VALIDATED"
                )

            # Get all pages
            pages = await self.pages.list_by_project(project_id)
            if not pages:
                raise PipelineError(
                    "No pages uploaded",
                    error_code="NO_PAGES"
                )

            # Single page projects: Option B - provisional only
            if len(pages) == 1:
                return await self._run_single_page_flow(project_id, pages[0])

            # Update status to processing
            await self.projects.update_status(project_id, ProjectStatus.PROCESSING)

            # Initialize guide storage
            guide = await self.guides.get_or_create(project_id)

            # Step 1: Build provisional guide from page 1
            logger.info(
                "pipeline_step",
                project_id=project_id_str,
                step="guide_builder",
                page=1,
            )

            page_1 = pages[0]
            page_1_bytes = await self.file_storage.read_image_bytes(page_1.file_path)

            builder_result = await self.guide_builder.build_guide(
                image_bytes=page_1_bytes,
                project_id=project_id_str,
            )

            if not builder_result.success:
                await self.projects.update_status(project_id, ProjectStatus.FAILED)
                raise PipelineError(
                    f"Guide builder failed: {builder_result.error}",
                    error_code="GUIDE_BUILDER_FAILED"
                )

            provisional_guide = builder_result.provisional_guide
            await self.guides.update_provisional(project_id, provisional_guide)

            # Step 2: Apply guide to remaining pages
            logger.info(
                "pipeline_step",
                project_id=project_id_str,
                step="guide_applier",
                pages=len(pages) - 1,
            )

            subsequent_pages = []
            for page in pages[1:]:
                page_bytes = await self.file_storage.read_image_bytes(page.file_path)
                subsequent_pages.append((page.order, page_bytes))

            applier_result = await self.guide_applier.validate_all_pages(
                pages=subsequent_pages,
                provisional_guide=provisional_guide,
                project_id=project_id_str,
            )

            # Collect validation reports (including failed ones for transparency)
            validation_reports = [
                (v.page_order, v.validation_report)
                for v in applier_result.page_validations
                if v.success
            ]

            if not validation_reports:
                await self.projects.update_status(project_id, ProjectStatus.FAILED)
                raise PipelineError(
                    "All page validations failed",
                    error_code="ALL_VALIDATIONS_FAILED"
                )

            # Step 3: Self-validate for stability
            logger.info(
                "pipeline_step",
                project_id=project_id_str,
                step="self_validator",
            )

            validator_result = await self.self_validator.validate_stability(
                provisional_guide=provisional_guide,
                validation_reports=validation_reports,
                project_id=project_id_str,
            )

            if not validator_result.success:
                await self.projects.update_status(project_id, ProjectStatus.FAILED)
                raise PipelineError(
                    f"Self-validation failed: {validator_result.error}",
                    error_code="SELF_VALIDATOR_FAILED"
                )

            confidence_report = validator_result.confidence_report
            await self.guides.update_confidence_report(project_id, confidence_report)

            # Step 4: Consolidate final guide
            logger.info(
                "pipeline_step",
                project_id=project_id_str,
                step="guide_consolidator",
                can_generate=confidence_report.can_generate_final,
            )

            consolidator_result = await self.guide_consolidator.consolidate_guide(
                provisional_guide=provisional_guide,
                confidence_report=confidence_report,
                raw_stability_analysis=validator_result.raw_analysis,
                project_id=project_id_str,
            )

            if not consolidator_result.success:
                await self.projects.update_status(project_id, ProjectStatus.FAILED)
                raise PipelineError(
                    f"Guide consolidation failed: {consolidator_result.error}",
                    error_code="CONSOLIDATOR_FAILED"
                )

            # Determine final status and result
            if consolidator_result.stable_guide:
                await self.guides.update_stable(
                    project_id,
                    consolidator_result.stable_guide,
                    confidence_report,
                )
                await self.projects.update_status(project_id, ProjectStatus.VALIDATED)

                logger.info(
                    "pipeline_complete",
                    project_id=project_id_str,
                    step="complete",
                    status="validated",
                    has_stable_guide=True,
                )

                return PipelineResult(
                    success=True,
                    has_stable_guide=True,
                    stable_guide=consolidator_result.stable_guide,
                    pages_processed=len(pages),
                )

            else:
                # Guide rejected due to instability - but provisional guide exists
                # Use PROVISIONAL_ONLY instead of FAILED to allow extraction
                await self.guides.update_stable(project_id, None, confidence_report)
                await self.projects.update_status(project_id, ProjectStatus.PROVISIONAL_ONLY)

                logger.info(
                    "pipeline_complete",
                    project_id=project_id_str,
                    step="complete",
                    status="rejected",
                    has_stable_guide=False,
                    reason=consolidator_result.rejection_message,
                )

                return PipelineResult(
                    success=True,  # Pipeline ran successfully
                    has_stable_guide=False,
                    rejection_message=consolidator_result.rejection_message,
                    pages_processed=len(pages),
                )

        except PipelineError:
            raise

        except Exception as e:
            logger.error(
                "pipeline_error",
                project_id=project_id_str,
                step="unknown",
                error=str(e),
            )

            try:
                await self.projects.update_status(project_id, ProjectStatus.FAILED)
            except Exception:
                pass

            raise PipelineError(
                f"Unexpected pipeline error: {e}",
                error_code="UNEXPECTED_ERROR"
            )

    async def _run_single_page_flow(
        self,
        project_id: UUID,
        page,
    ) -> PipelineResult:
        """
        Run Option B: Single-page provisional-only flow.

        With only one page, we cannot validate rules across multiple pages.
        We generate a provisional guide only, clearly marked as unvalidated.
        """
        project_id_str = str(project_id)

        logger.info(
            "pipeline_single_page_start",
            project_id=project_id_str,
            step="single_page_flow",
        )

        try:
            await self.projects.update_status(project_id, ProjectStatus.PROCESSING)

            # Initialize guide storage
            guide = await self.guides.get_or_create(project_id)

            # Build provisional guide from the single page
            page_bytes = await self.file_storage.read_image_bytes(page.file_path)

            builder_result = await self.guide_builder.build_guide(
                image_bytes=page_bytes,
                project_id=project_id_str,
            )

            if not builder_result.success:
                await self.projects.update_status(project_id, ProjectStatus.FAILED)
                raise PipelineError(
                    f"Guide builder failed: {builder_result.error}",
                    error_code="GUIDE_BUILDER_FAILED"
                )

            provisional_guide = builder_result.provisional_guide
            await self.guides.update_provisional(project_id, provisional_guide)

            # For single-page: stable = null, explicit rejection reason
            rejection_message = (
                "Cannot generate stable guide: Only 1 page provided. "
                "Validation requires at least 2 pages to test rule consistency. "
                "The provisional guide above contains candidate rules observed on page 1 "
                "but they have NOT been validated against other pages."
            )

            # Update status to PROVISIONAL_ONLY (not FAILED) since we have a provisional guide
            await self.projects.update_status(project_id, ProjectStatus.PROVISIONAL_ONLY)

            logger.info(
                "pipeline_single_page_complete",
                project_id=project_id_str,
                step="single_page_flow",
                status="provisional_only",
            )

            return PipelineResult(
                success=True,  # Pipeline ran successfully
                has_stable_guide=False,
                stable_guide=None,
                provisional_guide=provisional_guide,
                rejection_message=rejection_message,
                pages_processed=1,
                is_provisional_only=True,
            )

        except PipelineError:
            raise

        except Exception as e:
            logger.error(
                "pipeline_single_page_error",
                project_id=project_id_str,
                step="single_page_flow",
                error=str(e),
            )

            try:
                await self.projects.update_status(project_id, ProjectStatus.FAILED)
            except Exception:
                pass

            raise PipelineError(
                f"Single page flow error: {e}",
                error_code="SINGLE_PAGE_ERROR"
            )
