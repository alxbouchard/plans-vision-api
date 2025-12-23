"""V3 API routes - PDF master, mapping, and render endpoints.

Key principles:
- Render is PURE: zero model calls, geometry from mapping only
- PDF fingerprint mismatch must refuse (PDF_MISMATCH)
- Mapping required must refuse (MAPPING_REQUIRED)
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

import fitz  # PyMuPDF

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_tenant_id
from src.models.schemas_v3 import (
    SCHEMA_VERSION_V3,
    PDFUploadResponse,
    MappingJobResponse,
    MappingStatusResponse,
    MappingResponse,
    PageMapping,
    AffineTransform,
    RenderPDFRequest,
    RenderJobResponse,
    RenderStatusResponse,
    RenderTraceInfo,
    RenderAnnotationsRequest,
    RenderAnnotationsResponse,
    AnnotationItem,
    ErrorResponseV3,
)
from src.storage.database import (
    PDFMasterTable,
    MappingJobTable,
    PageMappingTable,
    RenderJobTable,
    ProjectTable,
    PageTable,
)
from src.config import get_settings
from src.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/v3", tags=["v3"])


def _error_response(
    status_code: int,
    error_code: str,
    message: str,
    recoverable: bool = True,
) -> JSONResponse:
    """Create a standardized V3 error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "schema_version": SCHEMA_VERSION_V3,
            "error_code": error_code,
            "message": message,
            "recoverable": recoverable,
        },
    )


# =============================================================================
# 1. Upload PDF Master
# =============================================================================

@router.post(
    "/projects/{project_id}/pdf",
    response_model=PDFUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pdf(
    project_id: UUID,
    file: UploadFile = File(...),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Upload PDF master document."""
    # Verify project exists and belongs to tenant
    result = await session.execute(
        select(ProjectTable).where(
            ProjectTable.id == str(project_id),
            ProjectTable.owner_id == str(tenant_id),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        return _error_response(404, "PROJECT_NOT_FOUND", "Project not found")

    # Validate file is PDF
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return _error_response(400, "INVALID_PDF", "File must be a PDF")

    # Read file content
    content = await file.read()
    if len(content) < 4 or content[:4] != b"%PDF":
        return _error_response(400, "INVALID_PDF", "Invalid PDF file format")

    # Compute fingerprint
    fingerprint = hashlib.sha256(content).hexdigest()

    # Count pages using PyMuPDF (single source of truth)
    try:
        pdf_doc = fitz.open(stream=content, filetype="pdf")
        page_count = pdf_doc.page_count
        pdf_doc.close()
    except Exception as e:
        return _error_response(400, "INVALID_PDF", f"Cannot read PDF: {str(e)}")

    # Save PDF to disk
    settings = get_settings()
    pdf_id = uuid4()
    pdf_dir = os.path.join(settings.upload_dir, str(project_id), "pdf")
    os.makedirs(pdf_dir, exist_ok=True)
    file_path = os.path.join(pdf_dir, f"{pdf_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(content)

    # Create database record
    pdf_record = PDFMasterTable(
        id=str(pdf_id),
        project_id=str(project_id),
        fingerprint=fingerprint,
        page_count=page_count,
        file_path=file_path,
        stored_at=datetime.utcnow(),
    )
    session.add(pdf_record)
    await session.commit()

    logger.info(
        "pdf_uploaded",
        project_id=str(project_id),
        pdf_id=str(pdf_id),
        page_count=page_count,
        fingerprint=fingerprint[:16],
    )

    return PDFUploadResponse(
        project_id=project_id,
        pdf_id=pdf_id,
        page_count=page_count,
        fingerprint=fingerprint,
        stored_at=datetime.utcnow(),
    )


# =============================================================================
# 2. Build Mapping
# =============================================================================

@router.post(
    "/projects/{project_id}/pdf/{pdf_id}/build-mapping",
    response_model=MappingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def build_mapping(
    project_id: UUID,
    pdf_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Start mapping job to convert PDF pages to PNG with coordinate transforms."""
    # Verify PDF exists
    result = await session.execute(
        select(PDFMasterTable).where(PDFMasterTable.id == str(pdf_id))
    )
    pdf = result.scalar_one_or_none()
    if not pdf or pdf.project_id != str(project_id):
        return _error_response(404, "PDF_NOT_FOUND", "PDF not found")

    # Create mapping job
    job_id = uuid4()
    mapping_version_id = uuid4()

    job = MappingJobTable(
        id=str(job_id),
        project_id=str(project_id),
        pdf_id=str(pdf_id),
        status="running",
        current_step="rasterize",
        mapping_version_id=str(mapping_version_id),
    )
    session.add(job)

    # Rasterize PDF pages to PNG using PyMuPDF
    settings = get_settings()
    # Absolute path for file I/O
    png_dir_abs = os.path.join(settings.upload_dir, str(project_id), "png")
    os.makedirs(png_dir_abs, exist_ok=True)
    # Relative path for PageTable.file_path (matches FileStorage convention)
    png_dir_rel = os.path.join(str(project_id), "png")

    # Open PDF for rasterization
    pdf_doc = fitz.open(pdf.file_path)

    # Create page mappings and PageTable rows for each page
    for page_num in range(1, pdf.page_count + 1):
        page_idx = page_num - 1
        page = pdf_doc[page_idx]

        # Get real PDF page geometry (all from page object, no hardcoding)
        rect = page.rect
        pdf_width_pt = rect.width
        pdf_height_pt = rect.height
        rotation = page.rotation

        # Get real mediabox and cropbox from PDF
        mediabox_rect = page.mediabox
        cropbox_rect = page.cropbox
        mediabox = [mediabox_rect.x0, mediabox_rect.y0, mediabox_rect.x1, mediabox_rect.y1]
        cropbox = [cropbox_rect.x0, cropbox_rect.y0, cropbox_rect.x1, cropbox_rect.y1]

        # Rasterize to PNG at 2x scale (fixed zoom, actual dimensions from pixmap)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        png_width = pix.width
        png_height = pix.height

        # Save PNG (use absolute path for file I/O)
        png_path_abs = os.path.join(png_dir_abs, f"page_{page_num}.png")
        pix.save(png_path_abs)
        # Relative path for database storage (matches FileStorage convention)
        png_path_rel = os.path.join(png_dir_rel, f"page_{page_num}.png")

        # Get PNG file stats for PageTable
        with open(png_path_abs, "rb") as f:
            png_bytes = f.read()
        byte_size = len(png_bytes)
        image_sha256 = hashlib.sha256(png_bytes).hexdigest()

        # Compute affine transform: PNG coords to PDF coords (derived from real dimensions)
        scale_x = pdf_width_pt / png_width
        scale_y = pdf_height_pt / png_height
        # Affine matrix [a, b, c, d, e, f] for: x' = ax + cy + e, y' = bx + dy + f
        matrix = [scale_x, 0, 0, scale_y, 0, 0]

        # Create PageMappingTable entry (stores absolute path for V3 render)
        page_mapping = PageMappingTable(
            id=str(uuid4()),
            mapping_version_id=str(mapping_version_id),
            pdf_id=str(pdf_id),
            page_number=page_num,
            png_width=png_width,
            png_height=png_height,
            pdf_width_pt=int(pdf_width_pt),
            pdf_height_pt=int(pdf_height_pt),
            rotation=rotation,
            mediabox_json=json.dumps(mediabox),
            cropbox_json=json.dumps(cropbox),
            transform_matrix_json=json.dumps(matrix),
            png_file_path=png_path_abs,
        )
        session.add(page_mapping)

        # Create PageTable entry for Phase 1 analyze compatibility
        # Uses relative path (matches FileStorage convention for read_image_bytes)
        page_entry = PageTable(
            id=str(uuid4()),
            project_id=str(project_id),
            order=page_num,
            file_path=png_path_rel,
            image_width=png_width,
            image_height=png_height,
            image_sha256=image_sha256,
            byte_size=byte_size,
        )
        session.add(page_entry)

    pdf_doc.close()

    # Mark job as completed
    job.status = "completed"
    job.current_step = None
    await session.commit()

    logger.info(
        "mapping_job_completed",
        project_id=str(project_id),
        pdf_id=str(pdf_id),
        mapping_version_id=str(mapping_version_id),
    )

    return MappingJobResponse(
        project_id=project_id,
        pdf_id=pdf_id,
        mapping_job_id=job_id,
        status="processing",  # Return as processing per contract
    )


@router.get(
    "/projects/{project_id}/pdf/{pdf_id}/mapping/status",
    response_model=MappingStatusResponse,
)
async def get_mapping_status(
    project_id: UUID,
    pdf_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get mapping job status."""
    result = await session.execute(
        select(MappingJobTable).where(
            MappingJobTable.pdf_id == str(pdf_id),
            MappingJobTable.project_id == str(project_id),
        ).order_by(MappingJobTable.created_at.desc())
    )
    job = result.scalar_one_or_none()

    if not job:
        return _error_response(404, "MAPPING_NOT_FOUND", "No mapping job found")

    errors = json.loads(job.errors_json) if job.errors_json else []

    return MappingStatusResponse(
        project_id=project_id,
        pdf_id=pdf_id,
        mapping_version_id=UUID(job.mapping_version_id) if job.mapping_version_id else None,
        overall_status=job.status,
        current_step=job.current_step,
        errors=errors,
    )


# =============================================================================
# 3. Get Mapping Metadata
# =============================================================================

@router.get(
    "/projects/{project_id}/pdf/{pdf_id}/mapping",
    response_model=MappingResponse,
)
async def get_mapping(
    project_id: UUID,
    pdf_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get coordinate mapping data."""
    # Get PDF for fingerprint
    result = await session.execute(
        select(PDFMasterTable).where(PDFMasterTable.id == str(pdf_id))
    )
    pdf = result.scalar_one_or_none()
    if not pdf or pdf.project_id != str(project_id):
        return _error_response(404, "PDF_NOT_FOUND", "PDF not found")

    # Get latest completed mapping job
    result = await session.execute(
        select(MappingJobTable).where(
            MappingJobTable.pdf_id == str(pdf_id),
            MappingJobTable.status == "completed",
        ).order_by(MappingJobTable.created_at.desc())
    )
    job = result.scalar_one_or_none()
    if not job:
        return _error_response(409, "MAPPING_REQUIRED", "No completed mapping available")

    # Get page mappings
    result = await session.execute(
        select(PageMappingTable).where(
            PageMappingTable.mapping_version_id == job.mapping_version_id
        ).order_by(PageMappingTable.page_number)
    )
    page_rows = result.scalars().all()

    pages = []
    for row in page_rows:
        matrix = json.loads(row.transform_matrix_json)
        pages.append(
            PageMapping(
                page_number=row.page_number,
                png_width=row.png_width,
                png_height=row.png_height,
                pdf_width_pt=float(row.pdf_width_pt),
                pdf_height_pt=float(row.pdf_height_pt),
                rotation=row.rotation,
                mediabox=json.loads(row.mediabox_json),
                cropbox=json.loads(row.cropbox_json),
                transform=AffineTransform(matrix=matrix),
            )
        )

    return MappingResponse(
        project_id=project_id,
        pdf_id=pdf_id,
        fingerprint=pdf.fingerprint,
        mapping_version_id=UUID(job.mapping_version_id),
        pages=pages,
    )


# =============================================================================
# 5. Render Annotated PDF
# =============================================================================

@router.post(
    "/projects/{project_id}/render/pdf",
    response_model=RenderJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def render_pdf(
    project_id: UUID,
    request: RenderPDFRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Render annotated PDF.

    This is a PURE operation: zero model calls.
    All geometry is derived from mapping_version_id.
    """
    pdf_id = request.pdf_id
    mapping_version_id = request.mapping_version_id

    # Verify PDF exists
    result = await session.execute(
        select(PDFMasterTable).where(PDFMasterTable.id == str(pdf_id))
    )
    pdf = result.scalar_one_or_none()
    if not pdf or pdf.project_id != str(project_id):
        return _error_response(409, "PDF_MISMATCH", "PDF not found or does not match project")

    # Verify mapping exists and matches
    result = await session.execute(
        select(MappingJobTable).where(
            MappingJobTable.mapping_version_id == str(mapping_version_id),
            MappingJobTable.pdf_id == str(pdf_id),
        )
    )
    mapping_job = result.scalar_one_or_none()
    if not mapping_job:
        return _error_response(409, "MAPPING_REQUIRED", "Mapping version not found")

    if mapping_job.status != "completed":
        return _error_response(409, "MAPPING_REQUIRED", "Mapping not yet completed")

    # Create render job
    render_job_id = uuid4()
    settings = get_settings()

    # Output path for annotated PDF
    output_dir = os.path.join(settings.upload_dir, str(project_id), "render")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{render_job_id}.pdf")

    # For now, copy original PDF as placeholder
    # In production, use PyMuPDF/reportlab to add annotations
    import shutil
    shutil.copy(pdf.file_path, output_path)

    # Create trace info
    trace = {
        "pdf_fingerprint": pdf.fingerprint,
        "mapping_version_id": str(mapping_version_id),
        "extraction_run_id": None,
    }

    render_job = RenderJobTable(
        id=str(render_job_id),
        project_id=str(project_id),
        pdf_id=str(pdf_id),
        mapping_version_id=str(mapping_version_id),
        status="completed",  # Synchronous for now
        output_pdf_path=output_path,
        request_json=request.model_dump_json(),
        trace_json=json.dumps(trace),
    )
    session.add(render_job)
    await session.commit()

    logger.info(
        "render_job_completed",
        project_id=str(project_id),
        render_job_id=str(render_job_id),
    )

    return RenderJobResponse(
        project_id=project_id,
        pdf_id=pdf_id,
        render_job_id=render_job_id,
        status="processing",  # Per contract, return as processing
    )


@router.get(
    "/projects/{project_id}/render/pdf/{render_job_id}",
    response_model=RenderStatusResponse,
)
async def get_render_status(
    project_id: UUID,
    render_job_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get render job status."""
    result = await session.execute(
        select(RenderJobTable).where(
            RenderJobTable.id == str(render_job_id),
            RenderJobTable.project_id == str(project_id),
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        return _error_response(404, "RENDER_NOT_FOUND", "Render job not found")

    trace = None
    if job.trace_json:
        trace_data = json.loads(job.trace_json)
        trace = RenderTraceInfo(
            pdf_fingerprint=trace_data["pdf_fingerprint"],
            mapping_version_id=UUID(trace_data["mapping_version_id"]),
            extraction_run_id=UUID(trace_data["extraction_run_id"]) if trace_data.get("extraction_run_id") else None,
        )

    # Generate URL (in production, this would be a signed URL or CDN path)
    output_url = None
    if job.output_pdf_path and os.path.exists(job.output_pdf_path):
        output_url = f"/files/{project_id}/render/{render_job_id}.pdf"

    return RenderStatusResponse(
        render_job_id=render_job_id,
        status=job.status,
        output_pdf_url=output_url,
        trace=trace,
    )


# =============================================================================
# 6. Render Annotations Only
# =============================================================================

@router.post(
    "/projects/{project_id}/render/annotations",
    response_model=RenderAnnotationsResponse,
)
async def render_annotations(
    project_id: UUID,
    request: RenderAnnotationsRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Export annotations without rendering PDF.

    This is a PURE operation: zero model calls.
    """
    pdf_id = request.pdf_id
    mapping_version_id = request.mapping_version_id

    # Verify PDF exists
    result = await session.execute(
        select(PDFMasterTable).where(PDFMasterTable.id == str(pdf_id))
    )
    pdf = result.scalar_one_or_none()
    if not pdf or pdf.project_id != str(project_id):
        return _error_response(409, "PDF_MISMATCH", "PDF not found or does not match project")

    # Verify mapping exists
    result = await session.execute(
        select(PageMappingTable).where(
            PageMappingTable.mapping_version_id == str(mapping_version_id)
        )
    )
    mappings = result.scalars().all()
    if not mappings:
        return _error_response(409, "MAPPING_REQUIRED", "Mapping not found")

    # For now, return empty annotations
    # In production, fetch from extraction results and transform coordinates
    annotations: List[AnnotationItem] = []

    return RenderAnnotationsResponse(
        pdf_id=pdf_id,
        format=request.format,
        annotations=annotations,
    )
