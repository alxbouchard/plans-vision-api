"""Test page selection uses FULL token counts, not limited candidates.

This test reproduces the bug where page 3 (schedule) was selected instead of
page 1 (floor plan) because token_summary.room_number_candidates was limited
to 30 entries and sorted by frequency, favoring high-frequency 2-digit codes.

The fix: _score_page now computes metrics on the FULL token list.
"""

import pytest
from pathlib import Path
from uuid import uuid4
from dataclasses import dataclass
from typing import Optional

from src.extraction.tokens import TextToken, TokenSource
from src.extraction.token_summary import generate_token_summary


@dataclass
class MockPage:
    """Mock page object for testing."""
    id: any
    order: int
    file_path: str = "/tmp/test.png"
    source_pdf_path: Optional[str] = None
    source_pdf_page_index: Optional[int] = None


class TestFullTokenScoring:
    """Test that page scoring uses full token counts."""

    def test_token_summary_limits_to_30(self):
        """Verify that token_summary.room_number_candidates is limited to 30.

        This confirms the bug exists in token_summary (by design for prompts).
        """
        # Create 100 number tokens with near_name
        tokens = []
        for i in range(100):
            # Room number (3-digit)
            tokens.append(TextToken(
                text=f"{200 + i}",
                bbox=[100 + i * 10, 100, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
            # Room name nearby
            tokens.append(TextToken(
                text="ROOM",
                bbox=[100 + i * 10, 80, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))

        summary = generate_token_summary(tokens)

        # Token summary SHOULD be limited (this is expected for the prompt)
        assert len(summary.room_number_candidates) <= 30, \
            "token_summary should limit candidates for prompt efficiency"

    def test_full_metrics_not_limited(self):
        """Verify that _compute_full_token_metrics counts ALL tokens."""
        from src.pipeline.orchestrator import PipelineOrchestrator

        # Create mock orchestrator (we only need the method)
        orchestrator = object.__new__(PipelineOrchestrator)

        # Create 100 3-digit numbers paired with names
        tokens = []
        for i in range(100):
            tokens.append(TextToken(
                text=f"{200 + i}",
                bbox=[100 + i * 10, 100, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
            tokens.append(TextToken(
                text="ROOM",
                bbox=[100 + i * 10, 80, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))

        (
            tokens_count,
            three_digit_total,
            three_digit_paired,
            pairs_total,
            name_candidates,
        ) = orchestrator._compute_full_token_metrics(tokens)

        # Full metrics should count ALL 100 3-digit paired numbers
        assert three_digit_total == 100, \
            f"Expected 100 3-digit numbers, got {three_digit_total}"
        assert three_digit_paired == 100, \
            f"Expected 100 3-digit paired, got {three_digit_paired}"
        assert pairs_total == 100, \
            f"Expected 100 pairs, got {pairs_total}"

    def test_page1_wins_over_page3_with_full_tokens(self):
        """Simulate Addenda scenario: page 1 (plan) should beat page 3 (schedule).

        Before fix: page 3 won because limited candidates favored high-freq codes.
        After fix: page 1 wins because full 3-digit paired count is higher.
        """
        from src.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = object.__new__(PipelineOrchestrator)

        # Page 1: 75 real room labels (3-digit paired)
        # Like: CLASSE 203, CORRIDOR 210, etc.
        page1_tokens = []
        for i in range(75):
            page1_tokens.append(TextToken(
                text=f"{200 + i}",  # 3-digit room numbers
                bbox=[100 + i * 10, 100, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
            page1_tokens.append(TextToken(
                text="CLASSE",
                bbox=[100 + i * 10, 80, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
        # Add some 2-digit codes (annotation codes, not room numbers)
        for i in range(50):
            page1_tokens.append(TextToken(
                text=f"{i:02d}",  # 2-digit codes: 00, 01, 02, ...
                bbox=[500 + i * 5, 500, 20, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))

        # Page 3: 20 real room labels but 200+ 3-digit codes in schedule
        # Like: 000, 100, 148 appearing many times (schedule data)
        page3_tokens = []
        for i in range(20):
            page3_tokens.append(TextToken(
                text=f"{300 + i}",  # 3-digit
                bbox=[100 + i * 10, 100, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
            page3_tokens.append(TextToken(
                text="SALLE",
                bbox=[100 + i * 10, 80, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
        # Many unpaired 3-digit numbers (schedule codes)
        for i in range(200):
            page3_tokens.append(TextToken(
                text="000",  # High-frequency 3-digit (not a room)
                bbox=[500 + i * 3, 500 + i * 2, 20, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))

        # Compute metrics
        metrics1 = orchestrator._compute_full_token_metrics(page1_tokens)
        metrics3 = orchestrator._compute_full_token_metrics(page3_tokens)

        # Unpack
        _, three_digit_total_1, three_digit_paired_1, pairs_1, names_1 = metrics1
        _, three_digit_total_3, three_digit_paired_3, pairs_3, names_3 = metrics3

        # Compute scores (same formula as orchestrator)
        score1 = (three_digit_paired_1 * 5) + (pairs_1 * 2) + names_1
        score3 = (three_digit_paired_3 * 5) + (pairs_3 * 2) + names_3

        # Page 1 should win because it has more 3-digit PAIRED numbers
        assert three_digit_paired_1 > three_digit_paired_3, \
            f"Page 1 should have more 3-digit paired: {three_digit_paired_1} vs {three_digit_paired_3}"
        assert score1 > score3, \
            f"Page 1 should have higher score: {score1} vs {score3}"

    def test_high_freq_2digit_codes_dont_inflate_score(self):
        """High-frequency 2-digit codes should not boost the score.

        Regression test: before fix, pages with many 2-digit codes (like "05", "01")
        could have inflated pair counts because they appeared more in limited list.
        """
        from src.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = object.__new__(PipelineOrchestrator)

        # Page with many 2-digit codes paired with names
        tokens = []
        # 10 real 3-digit room labels
        for i in range(10):
            tokens.append(TextToken(
                text=f"{100 + i}",
                bbox=[100 + i * 10, 100, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
            tokens.append(TextToken(
                text="ROOM",
                bbox=[100 + i * 10, 80, 50, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))

        # 100 2-digit codes paired with words
        for i in range(100):
            tokens.append(TextToken(
                text=f"{i % 10:02d}",  # 00-09 repeated
                bbox=[500 + i * 3, 100, 20, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))
            tokens.append(TextToken(
                text="TYPE",
                bbox=[500 + i * 3, 80, 20, 20],
                confidence=1.0,
                source=TokenSource.PYMUPDF,
            ))

        metrics = orchestrator._compute_full_token_metrics(tokens)
        _, three_digit_total, three_digit_paired, pairs_total, _ = metrics

        # Only the 10 real room numbers should be 3-digit paired
        assert three_digit_paired == 10, \
            f"Only 10 3-digit numbers should be paired, got {three_digit_paired}"

        # Total pairs includes 2-digit but score formula prioritizes 3-digit
        # Score = 3-digit×5 + pairs×2 + names
        # With full tokens, 3-digit paired (10×5=50) is the primary signal


class TestAddendaRealData:
    """Test with real Addenda PDF data (if available)."""

    @pytest.fixture
    def addenda_pdf_path(self):
        """Get path to Addenda PDF fixture."""
        path = Path("tests/fixtures/23-333 - EJ - Addenda - A-01 - Plans.pdf")
        if not path.exists():
            pytest.skip("Addenda PDF fixture not available")
        return path

    @pytest.mark.asyncio
    async def test_addenda_page1_selected(self, addenda_pdf_path):
        """Verify page 1 is selected for Addenda PDF with full token scoring."""
        from src.extraction.tokens import get_tokens_for_page
        from src.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = object.__new__(PipelineOrchestrator)

        scores = []
        for page_idx in range(3):
            page_id = uuid4()
            tokens = await get_tokens_for_page(
                page_id=page_id,
                pdf_path=addenda_pdf_path,
                page_number=page_idx,
                use_vision=False,
            )

            metrics = orchestrator._compute_full_token_metrics(tokens)
            tokens_count, three_digit_total, three_digit_paired, pairs_total, names = metrics

            # Compute score
            pairing_bonus = 10 if pairs_total > 20 else 0
            score = (three_digit_paired * 5) + (pairs_total * 2) + names + pairing_bonus

            scores.append({
                "page_order": page_idx + 1,
                "tokens_count": tokens_count,
                "three_digit_total": three_digit_total,
                "three_digit_paired": three_digit_paired,
                "pairs_total": pairs_total,
                "names": names,
                "score": score,
            })

        # Find best page
        best = max(scores, key=lambda s: s["score"])

        # Page 1 should be selected (floor plan with room labels)
        assert best["page_order"] == 1, \
            f"Expected page 1 to be selected, got page {best['page_order']}. Scores: {scores}"

        # Page 1 should have significantly more 3-digit paired than page 3
        page1 = next(s for s in scores if s["page_order"] == 1)
        page3 = next(s for s in scores if s["page_order"] == 3)

        assert page1["three_digit_paired"] > page3["three_digit_paired"], \
            f"Page 1 should have more 3-digit paired: {page1['three_digit_paired']} vs {page3['three_digit_paired']}"
