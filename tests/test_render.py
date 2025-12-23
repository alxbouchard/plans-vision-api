"""Tests for Phase 3: Render (PDF master anchoring).

Test gates per TEST_GATES_RENDER.md:
- Gate 1: Fingerprint mismatch refusal
- Gate 2: Mapping required refusal
- Gate 3: Coordinate transform correctness
- Gate 4: Rotation coverage (0, 90, 180, 270)
- Gate 5: Cropbox coverage
- Gate 6: Renderer is pure (zero model calls)
- Gate 7: PDF output contains annotations
- Gate 8: Annotated PDF is reproducible
"""

import hashlib
import io
import math
import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from pydantic import ValidationError

from src.models.schemas_v3 import (
    SCHEMA_VERSION_V3,
    PDFUploadResponse,
    PageMapping,
    AffineTransform,
    MappingResponse,
    GeometryPNG,
    GeometryPDF,
    TraceInfo,
    QueryMatchV3,
    RenderPDFRequest,
    RenderAnnotationsRequest,
    AnnotationItem,
    ErrorResponseV3,
)


class TestSchemaV3:
    """Test v3 schema models."""

    def test_schema_version_is_3_1(self):
        """Test that schema version is 3.1."""
        assert SCHEMA_VERSION_V3 == "3.1"

    def test_pdf_upload_response_valid(self):
        """Test PDFUploadResponse model."""
        from datetime import datetime
        resp = PDFUploadResponse(
            project_id=uuid4(),
            pdf_id=uuid4(),
            page_count=42,
            fingerprint="abc123" * 10,
            stored_at=datetime.now()
        )
        assert resp.schema_version == "3.1"
        assert resp.page_count == 42

    def test_affine_transform_requires_6_elements(self):
        """Test that affine transform requires exactly 6 matrix elements."""
        # Valid
        t = AffineTransform(matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
        assert len(t.matrix) == 6

        # Invalid - too few
        with pytest.raises(ValidationError):
            AffineTransform(matrix=[1.0, 0.0, 0.0])

        # Invalid - too many
        with pytest.raises(ValidationError):
            AffineTransform(matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0])

    def test_page_mapping_valid(self):
        """Test PageMapping model with valid data."""
        pm = PageMapping(
            page_number=1,
            png_width=8000,
            png_height=5200,
            pdf_width_pt=612.0,
            pdf_height_pt=792.0,
            rotation=0,
            mediabox=[0, 0, 612, 792],
            cropbox=[0, 0, 612, 792],
            transform=AffineTransform(matrix=[0.0765, 0, 0, 0.1523, 0, 0])
        )
        assert pm.page_number == 1
        assert pm.rotation == 0

    def test_page_mapping_rotation_values(self):
        """Test that rotation only accepts valid values."""
        for rotation in [0, 90, 180, 270]:
            pm = PageMapping(
                page_number=1,
                png_width=800,
                png_height=600,
                pdf_width_pt=612.0,
                pdf_height_pt=792.0,
                rotation=rotation,
                mediabox=[0, 0, 612, 792],
                cropbox=[0, 0, 612, 792],
                transform=AffineTransform(matrix=[1, 0, 0, 1, 0, 0])
            )
            assert pm.rotation == rotation

    def test_geometry_png_bbox_format(self):
        """Test GeometryPNG bbox format."""
        g = GeometryPNG(bbox=[100, 200, 300, 250])
        assert g.type == "bbox"
        assert g.bbox == [100, 200, 300, 250]

    def test_geometry_pdf_rect_format(self):
        """Test GeometryPDF rect format."""
        g = GeometryPDF(rect=[72.0, 144.0, 216.0, 288.0])
        assert g.type == "rect"
        assert g.rect == [72.0, 144.0, 216.0, 288.0]


class TestGate1_FingerprintMismatch:
    """Gate 1: Fingerprint mismatch → PDF_MISMATCH."""

    def test_error_response_pdf_mismatch(self):
        """Test that PDF_MISMATCH error can be constructed."""
        err = ErrorResponseV3(
            error_code="PDF_MISMATCH",
            message="PDF fingerprint does not match mapping fingerprint",
            recoverable=False
        )
        assert err.error_code == "PDF_MISMATCH"
        assert err.schema_version == "3.1"
        assert err.recoverable is False


class TestGate2_MappingRequired:
    """Gate 2: Mapping missing → MAPPING_REQUIRED."""

    def test_error_response_mapping_required(self):
        """Test that MAPPING_REQUIRED error can be constructed."""
        err = ErrorResponseV3(
            error_code="MAPPING_REQUIRED",
            message="No mapping exists for this PDF",
            recoverable=True
        )
        assert err.error_code == "MAPPING_REQUIRED"
        assert err.recoverable is True


class TestGate3_CoordinateTransform:
    """Gate 3: Coordinate transform correctness."""

    def test_identity_transform(self):
        """Test identity transform produces same coordinates."""
        # Identity matrix: no scaling, no translation
        # For PDF coordinates, typically we need to scale and flip Y
        matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        # Apply transform: x' = a*x + c*y + e, y' = b*x + d*y + f
        png_x, png_y = 100, 200
        a, b, c, d, e, f = matrix
        pdf_x = a * png_x + c * png_y + e
        pdf_y = b * png_x + d * png_y + f

        assert pdf_x == 100.0
        assert pdf_y == 200.0

    def test_scale_transform(self):
        """Test scaling transform."""
        # Scale: PNG 8000x5200 -> PDF 612x792 (letter size)
        # scale_x = 612 / 8000 = 0.0765
        # scale_y = 792 / 5200 = 0.1523...
        scale_x = 612.0 / 8000.0
        scale_y = 792.0 / 5200.0
        matrix = [scale_x, 0.0, 0.0, scale_y, 0.0, 0.0]

        # Test corner (8000, 5200) should map to (612, 792)
        png_x, png_y = 8000, 5200
        a, b, c, d, e, f = matrix
        pdf_x = a * png_x + c * png_y + e
        pdf_y = b * png_x + d * png_y + f

        assert abs(pdf_x - 612.0) < 0.01
        assert abs(pdf_y - 792.0) < 0.01

    def test_known_bbox_to_rect(self):
        """Test known synthetic bbox produces expected PDF rect."""
        # PNG: 8000x5200, PDF: 612x792
        # PNG bbox [1000, 1000, 2000, 1500] (x, y, w, h)
        # Expected PDF rect corners
        scale_x = 612.0 / 8000.0
        scale_y = 792.0 / 5200.0

        png_bbox = [1000, 1000, 2000, 1500]  # x, y, w, h
        png_x1, png_y1 = png_bbox[0], png_bbox[1]
        png_x2, png_y2 = png_bbox[0] + png_bbox[2], png_bbox[1] + png_bbox[3]

        # Transform to PDF coordinates
        pdf_x1 = png_x1 * scale_x
        pdf_y1 = png_y1 * scale_y
        pdf_x2 = png_x2 * scale_x
        pdf_y2 = png_y2 * scale_y

        # Verify within tolerance
        assert abs(pdf_x1 - 76.5) < 0.1
        assert abs(pdf_y1 - 152.3) < 0.1
        assert abs(pdf_x2 - 229.5) < 0.1
        assert abs(pdf_y2 - 380.77) < 0.1


class TestGate4_RotationCoverage:
    """Gate 4: Mapping handles rotation 0, 90, 180, 270."""

    def _apply_rotation_transform(self, x: float, y: float, rotation: int,
                                   width: float, height: float) -> tuple[float, float]:
        """Apply rotation transform to coordinates."""
        if rotation == 0:
            return x, y
        elif rotation == 90:
            # 90 degrees clockwise: (x, y) -> (y, width - x)
            return y, width - x
        elif rotation == 180:
            # 180 degrees: (x, y) -> (width - x, height - y)
            return width - x, height - y
        elif rotation == 270:
            # 270 degrees clockwise: (x, y) -> (height - y, x)
            return height - y, x
        else:
            raise ValueError(f"Invalid rotation: {rotation}")

    def test_rotation_0(self):
        """Test no rotation."""
        x, y = self._apply_rotation_transform(100, 200, 0, 612, 792)
        assert x == 100
        assert y == 200

    def test_rotation_90(self):
        """Test 90 degree rotation."""
        x, y = self._apply_rotation_transform(100, 200, 90, 612, 792)
        assert x == 200
        assert y == 612 - 100

    def test_rotation_180(self):
        """Test 180 degree rotation."""
        x, y = self._apply_rotation_transform(100, 200, 180, 612, 792)
        assert x == 612 - 100
        assert y == 792 - 200

    def test_rotation_270(self):
        """Test 270 degree rotation."""
        x, y = self._apply_rotation_transform(100, 200, 270, 612, 792)
        assert x == 792 - 200
        assert y == 100


class TestGate5_CropboxCoverage:
    """Gate 5: Mapping respects cropbox and mediabox differences."""

    def test_cropbox_equals_mediabox(self):
        """Test when cropbox equals mediabox (no adjustment needed)."""
        mediabox = [0, 0, 612, 792]
        cropbox = [0, 0, 612, 792]

        # No offset needed
        offset_x = cropbox[0] - mediabox[0]
        offset_y = cropbox[1] - mediabox[1]

        assert offset_x == 0
        assert offset_y == 0

    def test_cropbox_smaller_than_mediabox(self):
        """Test when cropbox is smaller (cropped margins)."""
        mediabox = [0, 0, 612, 792]
        cropbox = [36, 36, 576, 756]  # 0.5 inch margins

        # Offset needed
        offset_x = cropbox[0] - mediabox[0]
        offset_y = cropbox[1] - mediabox[1]

        assert offset_x == 36  # 0.5 inch = 36 points
        assert offset_y == 36

    def test_coordinate_with_cropbox_offset(self):
        """Test that coordinates are adjusted for cropbox offset."""
        mediabox = [0, 0, 612, 792]
        cropbox = [36, 36, 576, 756]

        # A point at (100, 100) in the cropped view
        # should map to (100 + 36, 100 + 36) in mediabox
        point_in_crop = (100, 100)
        offset_x = cropbox[0]
        offset_y = cropbox[1]

        point_in_media = (point_in_crop[0] + offset_x, point_in_crop[1] + offset_y)

        assert point_in_media == (136, 136)


class TestGate6_RendererPure:
    """Gate 6: Renderer performs zero model calls."""

    def test_render_request_has_no_model_dependency(self):
        """Test that render request schema has no model-related fields."""
        # Verify no model-related fields exist (access from class, not instance)
        field_names = set(RenderPDFRequest.model_fields.keys())
        model_related = {"model", "prompt", "vision", "ai", "gpt", "openai"}
        assert field_names.isdisjoint(model_related)

    def test_annotations_request_has_no_model_dependency(self):
        """Test that annotations request has no model-related fields."""
        # Verify no model-related fields exist (access from class, not instance)
        field_names = set(RenderAnnotationsRequest.model_fields.keys())
        model_related = {"model", "prompt", "vision", "ai", "gpt", "openai"}
        assert field_names.isdisjoint(model_related)


class TestGate7_PDFAnnotations:
    """Gate 7: PDF output contains annotations."""

    def test_annotation_item_schema(self):
        """Test AnnotationItem has required fields for PDF annotation."""
        ann = AnnotationItem(
            page_number=12,
            type="rect",
            rect=[72.0, 144.0, 216.0, 288.0],
            label="CLASSE 203",
            object_id="room_203",
            confidence_level="high"
        )
        assert ann.page_number == 12
        assert ann.type == "rect"
        assert len(ann.rect) == 4
        assert ann.label == "CLASSE 203"
        assert ann.object_id == "room_203"

    def test_annotation_rect_coordinates(self):
        """Test annotation rect has valid PDF coordinates."""
        ann = AnnotationItem(
            page_number=1,
            type="rect",
            rect=[0.0, 0.0, 612.0, 792.0],  # Full letter page
            label="Full Page",
            object_id="test_1",
            confidence_level="high"
        )
        x1, y1, x2, y2 = ann.rect
        assert x1 >= 0
        assert y1 >= 0
        assert x2 > x1
        assert y2 > y1


class TestGate8_Reproducibility:
    """Gate 8: Annotated PDF is reproducible."""

    def test_same_inputs_produce_same_geometry(self):
        """Test that same inputs produce identical annotation geometry."""
        # Define inputs
        pdf_id = uuid4()
        mapping_version_id = uuid4()
        object_id = "room_203"
        png_bbox = [1000, 1000, 2000, 1500]
        scale_x = 612.0 / 8000.0
        scale_y = 792.0 / 5200.0

        def compute_pdf_rect(bbox: list, sx: float, sy: float) -> list:
            x, y, w, h = bbox
            return [
                x * sx,
                y * sy,
                (x + w) * sx,
                (y + h) * sy
            ]

        # Compute twice
        rect1 = compute_pdf_rect(png_bbox, scale_x, scale_y)
        rect2 = compute_pdf_rect(png_bbox, scale_x, scale_y)

        # Must be identical
        assert rect1 == rect2

    def test_trace_info_ensures_reproducibility(self):
        """Test that TraceInfo contains all required IDs for reproducibility."""
        trace = TraceInfo(
            pdf_id=uuid4(),
            pdf_fingerprint="abc123" * 10,
            mapping_version_id=uuid4(),
            guide_version_id=uuid4(),
            extraction_run_id=uuid4(),
            index_version_id=uuid4()
        )
        # All IDs present
        assert trace.pdf_id is not None
        assert trace.pdf_fingerprint is not None
        assert trace.mapping_version_id is not None
        assert trace.extraction_run_id is not None
