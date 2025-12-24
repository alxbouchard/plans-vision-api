"""Regression tests for PageClassifier - Phase 2.

These tests verify the classifier fix that prevents 'unknown' for readable pages.

Unit tests run with OPENAI_API_KEY=dummy.
Integration tests require: RUN_INTEGRATION=1 AND valid OPENAI_API_KEY.
"""

import os
import pytest
from uuid import uuid4
from pathlib import Path
from unittest.mock import AsyncMock, patch
import json

from src.extraction.classifier import PageClassifier, CLASSIFIER_SYSTEM_PROMPT, CLASSIFIER_USER_PROMPT
from src.models.entities import PageType, ConfidenceLevel, PageClassification


# =============================================================================
# Unit tests for classifier fallback logic
# =============================================================================

class TestClassifierFallbackLogic:
    """Test that classifier never returns UNKNOWN for readable pages."""

    @pytest.mark.asyncio
    async def test_unknown_downgraded_to_detail(self):
        """If model returns 'unknown', downgrade to 'detail' with low confidence."""
        classifier = PageClassifier()
        page_id = uuid4()

        # Mock VisionClient to return 'unknown'
        with patch.object(classifier.client, 'analyze_image', new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps({
                "page_type": "unknown",
                "confidence": 0.8,
                "evidence": ["some evidence"]
            })

            result = await classifier.classify(page_id, b"fake_image_bytes")

            # Should downgrade to DETAIL
            assert result.page_type == PageType.DETAIL
            assert result.confidence <= 0.2  # Capped at 0.2
            assert result.confidence_level == ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_invalid_type_fallback_to_detail(self):
        """If model returns invalid type, fallback to 'detail'."""
        classifier = PageClassifier()
        page_id = uuid4()

        with patch.object(classifier.client, 'analyze_image', new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps({
                "page_type": "drawing",  # Invalid type
                "confidence": 0.9,
                "evidence": []
            })

            result = await classifier.classify(page_id, b"fake_image_bytes")

            assert result.page_type == PageType.DETAIL
            assert result.confidence == 0.2
            assert result.confidence_level == ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_json_parse_error_fallback(self):
        """If model returns invalid JSON, fallback to 'detail'."""
        classifier = PageClassifier()
        page_id = uuid4()

        with patch.object(classifier.client, 'analyze_image', new_callable=AsyncMock) as mock:
            mock.return_value = "This is not valid JSON"

            result = await classifier.classify(page_id, b"fake_image_bytes")

            assert result.page_type == PageType.DETAIL
            assert result.confidence == 0.2
            assert result.confidence_level == ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_exception_fallback_never_raises(self):
        """If any exception occurs, fallback to 'detail' instead of raising."""
        classifier = PageClassifier()
        page_id = uuid4()

        with patch.object(classifier.client, 'analyze_image', new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("Network error")

            # Should NOT raise - returns fallback
            result = await classifier.classify(page_id, b"fake_image_bytes")

            assert result.page_type == PageType.DETAIL
            assert result.confidence == 0.2
            assert result.confidence_level == ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_analyze_image_called_with_correct_kwargs(self):
        """Verify analyze_image is called with correct parameter names."""
        classifier = PageClassifier()
        page_id = uuid4()
        image_bytes = b"fake_image_bytes"

        with patch.object(classifier.client, 'analyze_image', new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps({
                "page_type": "plan",
                "confidence": 0.9,
                "evidence": []
            })

            await classifier.classify(page_id, image_bytes)

            # Verify analyze_image was called exactly once
            mock.assert_called_once()

            # Verify the kwargs
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["image_bytes"] == image_bytes
            assert call_kwargs["prompt"] == CLASSIFIER_USER_PROMPT
            assert call_kwargs["model"] == "gpt-5.2-pro"
            assert call_kwargs["system_prompt"] == CLASSIFIER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_valid_plan_classification(self):
        """Valid 'plan' classification works correctly."""
        classifier = PageClassifier()
        page_id = uuid4()

        with patch.object(classifier.client, 'analyze_image', new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps({
                "page_type": "plan",
                "confidence": 0.85,
                "evidence": ["floor layout", "room labels"]
            })

            result = await classifier.classify(page_id, b"fake_image_bytes")

            assert result.page_type == PageType.PLAN
            assert result.confidence == 0.85
            assert result.confidence_level == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_valid_schedule_classification(self):
        """Valid 'schedule' classification works correctly."""
        classifier = PageClassifier()
        page_id = uuid4()

        with patch.object(classifier.client, 'analyze_image', new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps({
                "page_type": "schedule",
                "confidence": 0.75,
                "evidence": ["table structure", "door schedule"]
            })

            result = await classifier.classify(page_id, b"fake_image_bytes")

            assert result.page_type == PageType.SCHEDULE
            assert result.confidence == 0.75
            assert result.confidence_level == ConfidenceLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_confidence_to_level_boundaries(self):
        """Test confidence level boundaries."""
        from src.extraction.classifier import _confidence_to_level

        # HIGH: >= 0.8
        assert _confidence_to_level(0.8) == ConfidenceLevel.HIGH
        assert _confidence_to_level(0.95) == ConfidenceLevel.HIGH

        # MEDIUM: 0.5 - 0.79
        assert _confidence_to_level(0.5) == ConfidenceLevel.MEDIUM
        assert _confidence_to_level(0.79) == ConfidenceLevel.MEDIUM

        # LOW: < 0.5
        assert _confidence_to_level(0.49) == ConfidenceLevel.LOW
        assert _confidence_to_level(0.2) == ConfidenceLevel.LOW
        assert _confidence_to_level(0.0) == ConfidenceLevel.LOW


class TestClassifierPrompt:
    """Test that system prompt enforces no 'unknown' for readable pages."""

    def test_prompt_forbids_unknown_for_readable(self):
        """System prompt must instruct that 'unknown' is only for unreadable pages."""
        assert "unknown" in CLASSIFIER_SYSTEM_PROMPT.lower()
        assert "unreadable" in CLASSIFIER_SYSTEM_PROMPT.lower() or "blank" in CLASSIFIER_SYSTEM_PROMPT.lower()
        # Prompt should NOT include 'unknown' as a valid output option
        assert '"page_type": "plan|schedule|notes|legend|detail"' in CLASSIFIER_SYSTEM_PROMPT

    def test_prompt_lists_five_types(self):
        """Prompt should list exactly 5 page types (not 6)."""
        # The output schema should show only 5 types
        assert "plan" in CLASSIFIER_SYSTEM_PROMPT
        assert "schedule" in CLASSIFIER_SYSTEM_PROMPT
        assert "notes" in CLASSIFIER_SYSTEM_PROMPT
        assert "legend" in CLASSIFIER_SYSTEM_PROMPT
        assert "detail" in CLASSIFIER_SYSTEM_PROMPT

    def test_prompt_uses_confidence_for_uncertainty(self):
        """Prompt should instruct to express uncertainty via confidence, not type."""
        assert "confidence" in CLASSIFIER_SYSTEM_PROMPT.lower()
        # Should have instruction about expressing uncertainty via confidence
        assert "uncertainty" in CLASSIFIER_SYSTEM_PROMPT.lower() or "uncertain" in CLASSIFIER_SYSTEM_PROMPT.lower()


# =============================================================================
# Integration tests with real PDF
# Requires: RUN_INTEGRATION=1 AND valid OPENAI_API_KEY
# =============================================================================

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "23-333 - EJ - Addenda - A-01 - Plans.pdf"

# Skip integration tests unless explicitly enabled with valid API key
SKIP_INTEGRATION = not (
    os.environ.get("RUN_INTEGRATION") == "1"
    and os.environ.get("OPENAI_API_KEY")
    and os.environ.get("OPENAI_API_KEY") != "dummy"
    and os.environ.get("OPENAI_API_KEY") != "test"
)


@pytest.mark.skipif(SKIP_INTEGRATION, reason="Integration tests require RUN_INTEGRATION=1 and valid OPENAI_API_KEY")
@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="Fixture PDF not available")
class TestClassifierRealPDF:
    """
    Integration tests with real Addenda A-01 PDF.

    Run with: RUN_INTEGRATION=1 OPENAI_API_KEY=<your-key> pytest tests/test_classifier_regression.py -v

    Requirements:
    1. Page 1 must classify as 'plan' with confidence > 0.35
    2. Page 3 must NOT return 'unknown'
    3. No page should return 'unknown' if readable
    """

    @pytest.fixture
    def pdf_bytes(self) -> bytes:
        return FIXTURE_PDF.read_bytes()

    @pytest.mark.asyncio
    async def test_page1_classified_as_plan(self, pdf_bytes):
        """Page 1 of Addenda must be classified as 'plan' with confidence > 0.35."""
        import fitz  # PyMuPDF

        # Extract page 1 as PNG
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        doc.close()

        classifier = PageClassifier()
        page_id = uuid4()

        result = await classifier.classify(page_id, png_bytes)

        print(f"Page 1: type={result.page_type.value}, confidence={result.confidence}")
        assert result.page_type == PageType.PLAN, f"Expected PLAN, got {result.page_type}"
        assert result.confidence > 0.35, f"Expected confidence > 0.35, got {result.confidence}"
        assert result.page_type != PageType.UNKNOWN, "Should never return UNKNOWN for readable page"

    @pytest.mark.asyncio
    async def test_page3_not_unknown(self, pdf_bytes):
        """Page 3 of Addenda must NOT return 'unknown'."""
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 3:
            doc.close()
            pytest.skip("PDF has less than 3 pages")

        page = doc[2]  # 0-indexed
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        doc.close()

        classifier = PageClassifier()
        page_id = uuid4()

        result = await classifier.classify(page_id, png_bytes)

        print(f"Page 3: type={result.page_type.value}, confidence={result.confidence}")
        assert result.page_type != PageType.UNKNOWN, f"Page 3 returned UNKNOWN, should be one of 5 types"

    @pytest.mark.asyncio
    async def test_no_page_returns_unknown(self, pdf_bytes):
        """No readable page should return 'unknown'."""
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        classifier = PageClassifier()

        for page_num in range(doc.page_count):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")

            page_id = uuid4()
            result = await classifier.classify(page_id, png_bytes)

            print(f"Page {page_num + 1}: type={result.page_type.value}, confidence={result.confidence}")
            assert result.page_type != PageType.UNKNOWN, \
                f"Page {page_num + 1} returned UNKNOWN, should be one of 5 types"

        doc.close()

    @pytest.mark.asyncio
    async def test_all_pages_have_valid_type(self, pdf_bytes):
        """All pages must have one of the 5 valid types."""
        import fitz

        valid_types = {PageType.PLAN, PageType.SCHEDULE, PageType.NOTES, PageType.LEGEND, PageType.DETAIL}

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        classifier = PageClassifier()

        for page_num in range(doc.page_count):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")

            page_id = uuid4()
            result = await classifier.classify(page_id, png_bytes)

            assert result.page_type in valid_types, \
                f"Page {page_num + 1} has invalid type {result.page_type}"

        doc.close()
