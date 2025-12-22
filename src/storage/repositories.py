"""Repository pattern implementations for data access."""

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.entities import (
    Project,
    ProjectStatus,
    Page,
    VisualGuide,
    ConfidenceReport,
)
from .database import ProjectTable, PageTable, VisualGuideTable


class ProjectRepository:
    """Repository for Project entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, owner_id: UUID) -> Project:
        """Create a new project."""
        project = Project(owner_id=owner_id)
        db_project = ProjectTable(
            id=str(project.id),
            status=project.status,
            owner_id=str(project.owner_id),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        self.session.add(db_project)
        await self.session.commit()
        return project

    async def get_by_id(self, project_id: UUID, owner_id: UUID) -> Optional[Project]:
        """Get a project by ID, scoped to owner (tenant isolation)."""
        result = await self.session.execute(
            select(ProjectTable).where(
                ProjectTable.id == str(project_id),
                ProjectTable.owner_id == str(owner_id),
            )
        )
        db_project = result.scalar_one_or_none()
        if db_project is None:
            return None
        return Project(
            id=UUID(db_project.id),
            status=db_project.status,
            owner_id=UUID(db_project.owner_id),
            created_at=db_project.created_at,
            updated_at=db_project.updated_at,
        )

    async def get_by_id_no_tenant(self, project_id: UUID) -> Optional[Project]:
        """Get a project by ID without tenant check (internal use only)."""
        result = await self.session.execute(
            select(ProjectTable).where(ProjectTable.id == str(project_id))
        )
        db_project = result.scalar_one_or_none()
        if db_project is None:
            return None
        return Project(
            id=UUID(db_project.id),
            status=db_project.status,
            owner_id=UUID(db_project.owner_id),
            created_at=db_project.created_at,
            updated_at=db_project.updated_at,
        )

    async def update_status(self, project_id: UUID, status: ProjectStatus) -> bool:
        """Update project status."""
        result = await self.session.execute(
            select(ProjectTable).where(ProjectTable.id == str(project_id))
        )
        db_project = result.scalar_one_or_none()
        if db_project is None:
            return False

        # Invariant: validated projects cannot go back to draft
        if db_project.status == ProjectStatus.VALIDATED and status == ProjectStatus.DRAFT:
            raise ValueError("Validated projects cannot return to draft status")

        db_project.status = status
        await self.session.commit()
        return True

    async def list_by_owner(self, owner_id: UUID) -> list[Project]:
        """List all projects for an owner."""
        result = await self.session.execute(
            select(ProjectTable).where(
                ProjectTable.owner_id == str(owner_id)
            ).order_by(ProjectTable.created_at.desc())
        )
        return [
            Project(
                id=UUID(db.id),
                status=db.status,
                owner_id=UUID(db.owner_id),
                created_at=db.created_at,
                updated_at=db.updated_at,
            )
            for db in result.scalars().all()
        ]

    async def get_page_count(self, project_id: UUID) -> int:
        """Get the number of pages in a project."""
        result = await self.session.execute(
            select(func.count(PageTable.id)).where(
                PageTable.project_id == str(project_id)
            )
        )
        return result.scalar() or 0


class PageRepository:
    """Repository for Page entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: UUID, file_path: str) -> Page:
        """Create a new page with auto-incremented order."""
        # Get next order number
        result = await self.session.execute(
            select(func.coalesce(func.max(PageTable.order), 0)).where(
                PageTable.project_id == str(project_id)
            )
        )
        next_order = (result.scalar() or 0) + 1

        page = Page(
            project_id=project_id,
            order=next_order,
            file_path=file_path,
        )
        db_page = PageTable(
            id=str(page.id),
            project_id=str(page.project_id),
            order=page.order,
            file_path=page.file_path,
            created_at=page.created_at,
        )
        self.session.add(db_page)
        await self.session.commit()
        return page

    async def get_by_id(self, page_id: UUID, project_id: UUID) -> Optional[Page]:
        """Get a page by ID within a project."""
        result = await self.session.execute(
            select(PageTable).where(
                PageTable.id == str(page_id),
                PageTable.project_id == str(project_id),
            )
        )
        db_page = result.scalar_one_or_none()
        if db_page is None:
            return None
        return Page(
            id=UUID(db_page.id),
            project_id=UUID(db_page.project_id),
            order=db_page.order,
            file_path=db_page.file_path,
            created_at=db_page.created_at,
        )

    async def list_by_project(self, project_id: UUID) -> list[Page]:
        """List all pages in a project, ordered."""
        result = await self.session.execute(
            select(PageTable).where(
                PageTable.project_id == str(project_id)
            ).order_by(PageTable.order)
        )
        return [
            Page(
                id=UUID(db.id),
                project_id=UUID(db.project_id),
                order=db.order,
                file_path=db.file_path,
                created_at=db.created_at,
            )
            for db in result.scalars().all()
        ]

    async def get_by_order(self, project_id: UUID, order: int) -> Optional[Page]:
        """Get a page by its order number within a project."""
        result = await self.session.execute(
            select(PageTable).where(
                PageTable.project_id == str(project_id),
                PageTable.order == order,
            )
        )
        db_page = result.scalar_one_or_none()
        if db_page is None:
            return None
        return Page(
            id=UUID(db_page.id),
            project_id=UUID(db_page.project_id),
            order=db_page.order,
            file_path=db_page.file_path,
            created_at=db_page.created_at,
        )


class VisualGuideRepository:
    """Repository for VisualGuide entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, project_id: UUID) -> VisualGuide:
        """Get existing guide or create a new one."""
        result = await self.session.execute(
            select(VisualGuideTable).where(
                VisualGuideTable.project_id == str(project_id)
            )
        )
        db_guide = result.scalar_one_or_none()

        if db_guide is None:
            guide = VisualGuide(project_id=project_id)
            db_guide = VisualGuideTable(
                id=str(guide.id),
                project_id=str(guide.project_id),
                provisional=None,
                stable=None,
                confidence_report_json=None,
                created_at=guide.created_at,
                updated_at=guide.updated_at,
            )
            self.session.add(db_guide)
            await self.session.commit()
            return guide

        confidence_report = None
        if db_guide.confidence_report_json:
            confidence_report = ConfidenceReport.model_validate_json(
                db_guide.confidence_report_json
            )

        return VisualGuide(
            id=UUID(db_guide.id),
            project_id=UUID(db_guide.project_id),
            provisional=db_guide.provisional,
            stable=db_guide.stable,
            confidence_report=confidence_report,
            created_at=db_guide.created_at,
            updated_at=db_guide.updated_at,
        )

    async def get_by_project(self, project_id: UUID) -> Optional[VisualGuide]:
        """Get visual guide for a project."""
        result = await self.session.execute(
            select(VisualGuideTable).where(
                VisualGuideTable.project_id == str(project_id)
            )
        )
        db_guide = result.scalar_one_or_none()
        if db_guide is None:
            return None

        confidence_report = None
        if db_guide.confidence_report_json:
            confidence_report = ConfidenceReport.model_validate_json(
                db_guide.confidence_report_json
            )

        return VisualGuide(
            id=UUID(db_guide.id),
            project_id=UUID(db_guide.project_id),
            provisional=db_guide.provisional,
            stable=db_guide.stable,
            confidence_report=confidence_report,
            created_at=db_guide.created_at,
            updated_at=db_guide.updated_at,
        )

    async def update_provisional(self, project_id: UUID, provisional: str) -> bool:
        """Update the provisional guide."""
        result = await self.session.execute(
            select(VisualGuideTable).where(
                VisualGuideTable.project_id == str(project_id)
            )
        )
        db_guide = result.scalar_one_or_none()
        if db_guide is None:
            return False

        db_guide.provisional = provisional
        await self.session.commit()
        return True

    async def update_stable(
        self,
        project_id: UUID,
        stable: Optional[str],
        confidence_report: ConfidenceReport,
    ) -> bool:
        """Update the stable guide and confidence report."""
        result = await self.session.execute(
            select(VisualGuideTable).where(
                VisualGuideTable.project_id == str(project_id)
            )
        )
        db_guide = result.scalar_one_or_none()
        if db_guide is None:
            return False

        # Invariant: stable guide is immutable once set
        if db_guide.stable is not None and stable is not None:
            raise ValueError("Stable guide is immutable once set")

        db_guide.stable = stable
        db_guide.confidence_report_json = confidence_report.model_dump_json()
        await self.session.commit()
        return True

    async def update_confidence_report(
        self,
        project_id: UUID,
        confidence_report: ConfidenceReport,
    ) -> bool:
        """Update only the confidence report."""
        result = await self.session.execute(
            select(VisualGuideTable).where(
                VisualGuideTable.project_id == str(project_id)
            )
        )
        db_guide = result.scalar_one_or_none()
        if db_guide is None:
            return False

        db_guide.confidence_report_json = confidence_report.model_dump_json()
        await self.session.commit()
        return True
