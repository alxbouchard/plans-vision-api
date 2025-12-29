"""Tests for token_summary module."""

import pytest
from uuid import uuid4

from src.extraction.tokens import TextToken, TokenSource
from src.extraction.token_summary import (
    generate_token_summary,
    ROOM_NAME_PATTERN,
    ROOM_NUMBER_PATTERN,
)


class TestPatterns:
    """Test regex patterns for room names and numbers."""

    def test_room_name_pattern_matches_uppercase(self):
        assert ROOM_NAME_PATTERN.match("CLASSE")
        assert ROOM_NAME_PATTERN.match("CORRIDOR")
        assert ROOM_NAME_PATTERN.match("CHAUFFERIE")
        assert ROOM_NAME_PATTERN.match("WC")

    def test_room_name_pattern_rejects_lowercase(self):
        assert not ROOM_NAME_PATTERN.match("Classe")
        assert not ROOM_NAME_PATTERN.match("corridor")

    def test_room_name_pattern_rejects_short(self):
        assert not ROOM_NAME_PATTERN.match("A")

    def test_room_name_pattern_rejects_numbers(self):
        assert not ROOM_NAME_PATTERN.match("A123")
        assert not ROOM_NAME_PATTERN.match("123A")

    def test_room_number_pattern_matches_digits(self):
        assert ROOM_NUMBER_PATTERN.match("12")
        assert ROOM_NUMBER_PATTERN.match("123")
        assert ROOM_NUMBER_PATTERN.match("1234")

    def test_room_number_pattern_rejects_single_digit(self):
        assert not ROOM_NUMBER_PATTERN.match("1")

    def test_room_number_pattern_rejects_five_digits(self):
        assert not ROOM_NUMBER_PATTERN.match("12345")


class TestTokenSummary:
    """Test token summary generation."""

    def _make_token(self, text: str, x: int, y: int, w: int = 50, h: int = 20) -> TextToken:
        return TextToken(
            text=text,
            bbox=[x, y, w, h],
            confidence=1.0,
            source=TokenSource.PYMUPDF,
            page_id=uuid4(),
        )

    def test_empty_tokens(self):
        summary = generate_token_summary([])
        assert summary.total_text_blocks == 0
        assert summary.room_name_candidates == []
        assert summary.room_number_candidates == []

    def test_room_name_candidates(self):
        tokens = [
            self._make_token("CLASSE", 100, 100),
            self._make_token("CLASSE", 200, 200),
            self._make_token("CORRIDOR", 300, 300),
        ]
        summary = generate_token_summary(tokens)

        assert summary.total_text_blocks == 3
        assert len(summary.room_name_candidates) == 2

        # CLASSE should be first (count=2)
        assert summary.room_name_candidates[0].text == "CLASSE"
        assert summary.room_name_candidates[0].count == 2

        # CORRIDOR second (count=1)
        assert summary.room_name_candidates[1].text == "CORRIDOR"
        assert summary.room_name_candidates[1].count == 1

    def test_room_number_candidates(self):
        tokens = [
            self._make_token("110", 100, 100),
            self._make_token("121", 200, 200),
            self._make_token("122", 300, 300),
        ]
        summary = generate_token_summary(tokens)

        assert len(summary.room_number_candidates) == 3

    def test_nearby_pairing(self):
        # Name at (100, 100), number at (100, 130) - 30px below
        tokens = [
            self._make_token("CLASSE", 100, 100),
            self._make_token("132", 100, 130),
        ]
        summary = generate_token_summary(tokens)

        assert len(summary.room_number_candidates) == 1
        assert summary.room_number_candidates[0].near_name == "CLASSE"
        assert summary.room_number_candidates[0].distance_px is not None
        assert summary.room_number_candidates[0].distance_px < 50

    def test_pairing_pattern_detection(self):
        # Multiple name-number pairs, all with number below
        tokens = [
            self._make_token("CLASSE", 100, 100),
            self._make_token("132", 100, 130),
            self._make_token("CORRIDOR", 300, 100),
            self._make_token("133", 300, 130),
            self._make_token("BUREAU", 500, 100),
            self._make_token("134", 500, 130),
        ]
        summary = generate_token_summary(tokens)

        assert summary.pairing_pattern is not None
        assert summary.pairing_pattern.observed_relation == "number_below_name"
        assert summary.pairing_pattern.confidence in ("high", "medium")

    def test_high_frequency_noise_detection(self):
        # "05" appears 15 times - should be flagged as noise
        tokens = [self._make_token("05", i * 10, i * 10) for i in range(15)]
        summary = generate_token_summary(tokens)

        assert len(summary.high_frequency_numbers) == 1
        assert summary.high_frequency_numbers[0].text == "05"
        assert summary.high_frequency_numbers[0].count == 15

    def test_to_prompt_text(self):
        tokens = [
            self._make_token("CLASSE", 100, 100),
            self._make_token("132", 100, 130),
        ]
        summary = generate_token_summary(tokens)
        text = summary.to_prompt_text()

        assert "CLASSE" in text
        assert "132" in text
        assert "Total text blocks: 2" in text
