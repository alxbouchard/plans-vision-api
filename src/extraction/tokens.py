"""Unified token extraction for Phase 3.5.

Per WORK_QUEUE_PHASE3_5_ROOMS.md:
- All text sources produce TextToken in same pixel coordinate space
- Priority: PyMuPDF > Vision > OCR
- No hardcoded semantics - tokens are raw data

Constraints:
- All bbox in pixel space (same as stored PNG)
- Confidence reflects source reliability
- Source field enables debugging and priority
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from src.logging import get_logger

logger = get_logger(__name__)


class TokenSource(str, Enum):
    """Source of a text token."""
    PYMUPDF = "pymupdf"      # Vector text from PDF (highest priority)
    VISION = "vision"        # Vision model detection
    OCR = "ocr"              # OCR fallback (lowest priority)


class TextToken(BaseModel):
    """A unified text token from any source.

    All coordinates are in pixel space matching the stored PNG.
    """
    text: str = Field(description="The detected text content")
    bbox: list[int] = Field(
        min_length=4, max_length=4,
        description="Bounding box [x, y, width, height] in pixels"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, default=1.0,
        description="Detection confidence (1.0 for vector text)"
    )
    source: TokenSource = Field(description="Source of this token")
    page_id: Optional[UUID] = Field(default=None, description="Page ID if known")

    @property
    def text_lines(self) -> list[str]:
        """Return text as lines for compatibility with SpatialRoomLabeler."""
        return self.text.split("\n")


class PageRasterSpec(BaseModel):
    """Specification for page rasterization.

    Defines the target pixel space for all token coordinates.
    """
    width_px: int = Field(description="Page width in pixels")
    height_px: int = Field(description="Page height in pixels")
    dpi: int = Field(default=150, description="Resolution in DPI")
    rotation: int = Field(default=0, description="Page rotation in degrees")


class TokenProvider(ABC):
    """Abstract base for token providers.

    Each provider extracts text tokens from a specific source
    and normalizes coordinates to pixel space.
    """

    @abstractmethod
    async def get_tokens(
        self,
        page_id: UUID,
        image_bytes: Optional[bytes] = None,
        pdf_path: Optional[Path] = None,
        page_number: Optional[int] = None,
        raster_spec: Optional[PageRasterSpec] = None,
    ) -> list[TextToken]:
        """Extract tokens from the given page.

        Args:
            page_id: Page identifier
            image_bytes: PNG image bytes (for vision/OCR)
            pdf_path: Path to PDF file (for PyMuPDF)
            page_number: Page number in PDF (0-indexed)
            raster_spec: Target pixel space specification

        Returns:
            List of TextToken in pixel coordinates
        """
        pass


class PyMuPDFTokenProvider(TokenProvider):
    """Extract text tokens from PDF using PyMuPDF.

    This is the highest priority source - vector text is exact.
    Coordinates are converted from PDF points to pixels.
    """

    async def get_tokens(
        self,
        page_id: UUID,
        image_bytes: Optional[bytes] = None,
        pdf_path: Optional[Path] = None,
        page_number: Optional[int] = None,
        raster_spec: Optional[PageRasterSpec] = None,
    ) -> list[TextToken]:
        """Extract text tokens from PDF page."""
        if pdf_path is None:
            logger.debug(
                "pymupdf_no_pdf_path",
                page_id=str(page_id),
            )
            return []

        if page_number is None:
            page_number = 0

        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning(
                "pymupdf_not_installed",
                page_id=str(page_id),
            )
            return []

        try:
            doc = fitz.open(str(pdf_path))
            if page_number >= len(doc):
                logger.warning(
                    "pymupdf_page_out_of_range",
                    page_id=str(page_id),
                    page_number=page_number,
                    total_pages=len(doc),
                )
                doc.close()
                return []

            page = doc[page_number]

            # Get page dimensions in points
            rect = page.rect
            pdf_width = rect.width
            pdf_height = rect.height

            # Determine target pixel dimensions
            if raster_spec:
                target_width = raster_spec.width_px
                target_height = raster_spec.height_px
            else:
                # Default: 150 DPI
                dpi = 150
                target_width = int(pdf_width * dpi / 72)
                target_height = int(pdf_height * dpi / 72)

            # Scale factors for coordinate conversion
            scale_x = target_width / pdf_width
            scale_y = target_height / pdf_height

            # Extract words with bounding boxes
            words = page.get_text("words")  # Returns list of (x0, y0, x1, y1, word, block_no, line_no, word_no)

            tokens = []
            for word_data in words:
                x0, y0, x1, y1, text, block_no, line_no, word_no = word_data

                # Skip empty text
                if not text.strip():
                    continue

                # Convert PDF coordinates to pixels
                px_x = int(x0 * scale_x)
                px_y = int(y0 * scale_y)
                px_w = int((x1 - x0) * scale_x)
                px_h = int((y1 - y0) * scale_y)

                # Ensure non-zero dimensions
                px_w = max(px_w, 1)
                px_h = max(px_h, 1)

                token = TextToken(
                    text=text.strip(),
                    bbox=[px_x, px_y, px_w, px_h],
                    confidence=1.0,  # Vector text is exact
                    source=TokenSource.PYMUPDF,
                    page_id=page_id,
                )
                tokens.append(token)

            doc.close()

            logger.info(
                "pymupdf_tokens_extracted",
                page_id=str(page_id),
                tokens_count=len(tokens),
                pdf_path=str(pdf_path),
                page_number=page_number,
            )

            return tokens

        except Exception as e:
            logger.error(
                "pymupdf_extraction_error",
                page_id=str(page_id),
                error=str(e),
            )
            return []


class VisionTokenProvider(TokenProvider):
    """Wrap TextBlockDetector as a TokenProvider.

    Used when PDF is not available or has no vector text.
    """

    def __init__(self, use_vision: bool = True):
        self.use_vision = use_vision

    async def get_tokens(
        self,
        page_id: UUID,
        image_bytes: Optional[bytes] = None,
        pdf_path: Optional[Path] = None,
        page_number: Optional[int] = None,
        raster_spec: Optional[PageRasterSpec] = None,
    ) -> list[TextToken]:
        """Extract tokens using vision model."""
        if not self.use_vision or image_bytes is None:
            return []

        from src.extraction.text_block_detector import TextBlockDetector

        detector = TextBlockDetector(use_vision=True)

        try:
            blocks = await detector.detect(page_id, image_bytes)

            tokens = []
            for block in blocks:
                token = TextToken(
                    text=block.text,
                    bbox=list(block.bbox),
                    confidence=block.confidence,
                    source=TokenSource.VISION,
                    page_id=page_id,
                )
                tokens.append(token)

            logger.info(
                "vision_tokens_extracted",
                page_id=str(page_id),
                tokens_count=len(tokens),
            )

            return tokens

        except Exception as e:
            logger.error(
                "vision_token_extraction_error",
                page_id=str(page_id),
                error=str(e),
            )
            return []


class TokenMerger:
    """Merge tokens from multiple sources with deduplication.

    Priority: PyMuPDF > Vision > OCR
    Dedup by IoU > threshold and similar text.
    """

    def __init__(self, iou_threshold: float = 0.5):
        self.iou_threshold = iou_threshold

    def merge(self, *token_lists: list[TextToken]) -> list[TextToken]:
        """Merge multiple token lists with deduplication.

        Args:
            token_lists: Variable number of token lists (in priority order)

        Returns:
            Merged and deduplicated token list
        """
        # Flatten all tokens with source priority
        all_tokens: list[TextToken] = []
        for tokens in token_lists:
            all_tokens.extend(tokens)

        if not all_tokens:
            return []

        # Sort by source priority (pymupdf first)
        priority = {
            TokenSource.PYMUPDF: 0,
            TokenSource.VISION: 1,
            TokenSource.OCR: 2,
        }
        all_tokens.sort(key=lambda t: priority.get(t.source, 99))

        # Deduplicate
        merged: list[TextToken] = []
        for token in all_tokens:
            if not self._is_duplicate(token, merged):
                merged.append(token)

        # Log merge stats
        by_source = {}
        for t in merged:
            by_source[t.source.value] = by_source.get(t.source.value, 0) + 1

        logger.info(
            "tokens_merged",
            tokens_count_by_source=by_source,
            tokens_final_count=len(merged),
        )

        return merged

    def _is_duplicate(self, token: TextToken, existing: list[TextToken]) -> bool:
        """Check if token is a duplicate of any existing token."""
        for existing_token in existing:
            if self._compute_iou(token.bbox, existing_token.bbox) > self.iou_threshold:
                # Check text similarity
                if self._text_similar(token.text, existing_token.text):
                    return True
        return False

    def _compute_iou(self, bbox1: list[int], bbox2: list[int]) -> float:
        """Compute Intersection over Union of two bboxes."""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        # Convert to corners
        x1_max, y1_max = x1 + w1, y1 + h1
        x2_max, y2_max = x2 + w2, y2 + h2

        # Intersection
        xi = max(x1, x2)
        yi = max(y1, y2)
        xi_max = min(x1_max, x2_max)
        yi_max = min(y1_max, y2_max)

        if xi >= xi_max or yi >= yi_max:
            return 0.0

        intersection = (xi_max - xi) * (yi_max - yi)

        # Union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection

        if union <= 0:
            return 0.0

        return intersection / union

    def _text_similar(self, text1: str, text2: str) -> bool:
        """Check if two texts are similar."""
        t1 = text1.strip().upper()
        t2 = text2.strip().upper()

        # Exact match
        if t1 == t2:
            return True

        # One contains the other
        if t1 in t2 or t2 in t1:
            return True

        return False


async def get_tokens_for_page(
    page_id: UUID,
    image_bytes: Optional[bytes] = None,
    pdf_path: Optional[Path] = None,
    page_number: Optional[int] = None,
    raster_spec: Optional[PageRasterSpec] = None,
    use_vision: bool = True,
) -> list[TextToken]:
    """Get tokens for a page using all available sources.

    This is the main entry point for token extraction.
    Tries PyMuPDF first, falls back to Vision if needed.

    Args:
        page_id: Page identifier
        image_bytes: PNG image bytes
        pdf_path: Path to PDF file
        page_number: Page number in PDF (0-indexed)
        raster_spec: Target pixel space specification
        use_vision: Whether to use vision fallback

    Returns:
        Merged list of TextToken in pixel coordinates
    """
    pymupdf_provider = PyMuPDFTokenProvider()
    vision_provider = VisionTokenProvider(use_vision=use_vision)
    merger = TokenMerger()

    # Try PyMuPDF first
    pymupdf_tokens = await pymupdf_provider.get_tokens(
        page_id=page_id,
        pdf_path=pdf_path,
        page_number=page_number,
        raster_spec=raster_spec,
    )

    # If PyMuPDF got tokens, use them (no vision needed)
    if pymupdf_tokens:
        logger.info(
            "tokens_source_pymupdf",
            page_id=str(page_id),
            tokens_count=len(pymupdf_tokens),
            vision_skipped=True,
        )
        return pymupdf_tokens

    # Fallback to vision
    vision_tokens = await vision_provider.get_tokens(
        page_id=page_id,
        image_bytes=image_bytes,
        raster_spec=raster_spec,
    )

    if vision_tokens:
        logger.info(
            "tokens_source_vision",
            page_id=str(page_id),
            tokens_count=len(vision_tokens),
        )
        return vision_tokens

    logger.warning(
        "no_tokens_found",
        page_id=str(page_id),
        pymupdf_tried=pdf_path is not None,
        vision_tried=use_vision and image_bytes is not None,
    )
    return []
