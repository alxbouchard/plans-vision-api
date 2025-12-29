"""Database setup and session management."""

from __future__ import annotations

from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import UUID

from sqlalchemy import String, Integer, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.config import get_settings
from src.models.entities import ProjectStatus


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class ProjectTable(Base):
    """SQLAlchemy model for projects."""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(
        SQLEnum(ProjectStatus),
        default=ProjectStatus.DRAFT
    )
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pages: Mapped[list["PageTable"]] = relationship(
        "PageTable",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    visual_guide: Mapped["VisualGuideTable"] = relationship(
        "VisualGuideTable",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan"
    )


class PageTable(Base):
    """SQLAlchemy model for pages."""
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True
    )
    order: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Image metadata (Phase 2 bugfix)
    image_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Page classification (Phase 3.2 fix - persisted instead of in-memory)
    page_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    classification_confidence: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)  # stored as int * 1000
    classified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # PDF source association (Phase 3.5 - tokens-first extraction)
    source_pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_pdf_page_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    project: Mapped["ProjectTable"] = relationship("ProjectTable", back_populates="pages")


class VisualGuideTable(Base):
    """SQLAlchemy model for visual guides."""
    __tablename__ = "visual_guides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )
    provisional: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stable: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_report_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Phase 3.3: Store structured output with payloads for extraction
    stable_rules_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["ProjectTable"] = relationship("ProjectTable", back_populates="visual_guide")


# =============================================================================
# V3 Tables: PDF Master, Mapping, Render
# =============================================================================

class PDFMasterTable(Base):
    """SQLAlchemy model for PDF master documents."""
    __tablename__ = "pdf_masters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)  # SHA256
    page_count: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(512))
    stored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MappingJobTable(Base):
    """SQLAlchemy model for mapping jobs (PDF to PNG conversion)."""
    __tablename__ = "mapping_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    pdf_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pdf_masters.id", ondelete="CASCADE"),
        index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|failed
    current_step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    errors_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mapping_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PageMappingTable(Base):
    """SQLAlchemy model for per-page mapping data."""
    __tablename__ = "page_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mapping_version_id: Mapped[str] = mapped_column(String(36), index=True)
    pdf_id: Mapped[str] = mapped_column(String(36), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    png_width: Mapped[int] = mapped_column(Integer)
    png_height: Mapped[int] = mapped_column(Integer)
    pdf_width_pt: Mapped[float] = mapped_column(Integer)  # stored as int, converted to float
    pdf_height_pt: Mapped[float] = mapped_column(Integer)
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    mediabox_json: Mapped[str] = mapped_column(Text)
    cropbox_json: Mapped[str] = mapped_column(Text)
    transform_matrix_json: Mapped[str] = mapped_column(Text)  # [a,b,c,d,e,f]
    png_file_path: Mapped[str] = mapped_column(String(512))


class RenderJobTable(Base):
    """SQLAlchemy model for render jobs."""
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    pdf_id: Mapped[str] = mapped_column(String(36), index=True)
    mapping_version_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    output_pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    request_json: Mapped[str] = mapped_column(Text)  # serialized request
    trace_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Engine and session factory (initialized lazily)
_engine = None
AsyncSessionLocal = None


async def init_database() -> None:
    """Initialize the database and create tables."""
    global _engine, AsyncSessionLocal

    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    AsyncSessionLocal = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    if AsyncSessionLocal is None:
        await init_database()
    async with AsyncSessionLocal() as session:
        yield session


from contextlib import asynccontextmanager


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as a context manager."""
    if AsyncSessionLocal is None:
        await init_database()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
