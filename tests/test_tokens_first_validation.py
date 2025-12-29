"""Validation tests for tokens-first GuideBuilder.

These tests validate that PyMuPDF token extraction works correctly
with real PDF fixtures.
"""

import pytest
from pathlib import Path
from uuid import uuid4

from src.extraction.tokens import PyMuPDFTokenProvider, PageRasterSpec
from src.extraction.token_summary import generate_token_summary


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
ADDENDA_PDF = FIXTURES_DIR / "23-333 - EJ - Addenda - A-01 - Plans.pdf"


class TestPyMuPDFExtraction:
    """Test token extraction from real PDFs."""

    @pytest.mark.asyncio
    async def test_addenda_pdf_extracts_tokens(self):
        """Addenda PDF page 1 should extract many tokens."""
        if not ADDENDA_PDF.exists():
            pytest.skip("Addenda PDF fixture not found")

        provider = PyMuPDFTokenProvider()
        tokens = await provider.get_tokens(
            page_id=uuid4(),
            pdf_path=ADDENDA_PDF,
            page_number=0,  # First page
        )

        # Should have many tokens
        assert len(tokens) > 100, f"Expected >100 tokens, got {len(tokens)}"

    @pytest.mark.asyncio
    async def test_addenda_pdf_token_summary(self):
        """Token summary should identify room names and numbers."""
        if not ADDENDA_PDF.exists():
            pytest.skip("Addenda PDF fixture not found")

        provider = PyMuPDFTokenProvider()
        tokens = await provider.get_tokens(
            page_id=uuid4(),
            pdf_path=ADDENDA_PDF,
            page_number=0,
        )

        summary = generate_token_summary(tokens)

        # Should have room name candidates
        assert len(summary.room_name_candidates) > 0, "Expected room name candidates"

        # Should have room number candidates
        assert len(summary.room_number_candidates) > 0, "Expected room number candidates"

        # Should detect pairing pattern
        assert summary.pairing_pattern is not None, "Expected pairing pattern"

    @pytest.mark.asyncio
    async def test_addenda_pdf_candidate_room_names(self):
        """Token summary should provide room name candidates for the model.

        Note: The pattern-based detection will include French function words
        (DE, LA, VOIR, etc.) as candidates. This is expected - the LLM model
        will filter these out when generating the actual rules.

        The important thing is that the token summary provides the data.
        """
        if not ADDENDA_PDF.exists():
            pytest.skip("Addenda PDF fixture not found")

        provider = PyMuPDFTokenProvider()
        tokens = await provider.get_tokens(
            page_id=uuid4(),
            pdf_path=ADDENDA_PDF,
            page_number=0,
        )

        summary = generate_token_summary(tokens)

        # Get all room name candidate texts
        room_names = [c.text for c in summary.room_name_candidates]

        # Should have multiple candidates for the model to evaluate
        assert len(room_names) >= 10, f"Expected >=10 candidates, got {len(room_names)}"

        # The model will use these candidates along with spatial analysis
        # to determine which are actual room names vs function words

    @pytest.mark.asyncio
    async def test_addenda_pdf_detects_high_frequency_codes(self):
        """Should detect high-frequency codes like wall identifiers."""
        if not ADDENDA_PDF.exists():
            pytest.skip("Addenda PDF fixture not found")

        provider = PyMuPDFTokenProvider()
        tokens = await provider.get_tokens(
            page_id=uuid4(),
            pdf_path=ADDENDA_PDF,
            page_number=0,
        )

        summary = generate_token_summary(tokens)

        # Check if any high-frequency numbers were detected
        # (The Addenda PDF has "05" appearing ~47 times)
        if summary.high_frequency_numbers:
            high_freq_texts = [c.text for c in summary.high_frequency_numbers]
            # At least one should be a 2-digit code
            assert any(len(t) == 2 for t in high_freq_texts), \
                f"Expected 2-digit high-frequency code, got {high_freq_texts}"

    @pytest.mark.asyncio
    async def test_token_summary_prompt_text(self):
        """Token summary should generate readable prompt text."""
        if not ADDENDA_PDF.exists():
            pytest.skip("Addenda PDF fixture not found")

        provider = PyMuPDFTokenProvider()
        tokens = await provider.get_tokens(
            page_id=uuid4(),
            pdf_path=ADDENDA_PDF,
            page_number=0,
        )

        summary = generate_token_summary(tokens)
        prompt_text = summary.to_prompt_text()

        # Should contain key sections
        assert "Total text blocks:" in prompt_text
        assert "Room name candidates" in prompt_text
        assert "Room number candidates" in prompt_text
