"""Token summary generator for GuideBuilder.

Per TICKET_TOKENS_FIRST_GUIDE_BUILDER.md Step C:
- Aggregate tokens into structured summary
- Identify room_name candidates (uppercase words)
- Identify room_number candidates (2-4 digit numbers)
- Detect nearby pairs (name + number)
- Flag high-frequency noise

Constraints:
- No hardcoded room name lists
- Pattern detection only (regex-based)
- No semantic assumptions
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field

from src.extraction.tokens import TextToken
from src.logging import get_logger

logger = get_logger(__name__)


# Pattern for room names: 2+ uppercase letters (French accents included)
ROOM_NAME_PATTERN = re.compile(r"^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]{2,}$")

# Pattern for room numbers: 2-4 digits
ROOM_NUMBER_PATTERN = re.compile(r"^\d{2,4}$")

# High frequency threshold for noise detection
HIGH_FREQUENCY_THRESHOLD = 10


class RoomNameCandidate(BaseModel):
    """A candidate room name token."""
    text: str
    count: int
    example_bbox: list[int] = Field(min_length=4, max_length=4)


class RoomNumberCandidate(BaseModel):
    """A candidate room number token with optional nearby name."""
    text: str
    count: int
    near_name: Optional[str] = None
    distance_px: Optional[int] = None


class HighFrequencyCode(BaseModel):
    """A high-frequency code (likely noise)."""
    text: str
    count: int
    note: str = "likely wall/partition code"


class PairingPattern(BaseModel):
    """Observed pairing pattern between names and numbers."""
    observed_relation: str  # "number_below_name", "number_right_of_name", etc.
    typical_distance_px: tuple[int, int]  # (min, max)
    confidence: str  # "high", "medium", "low"
    sample_pairs: list[tuple[str, str]] = Field(default_factory=list)


class TokenSummary(BaseModel):
    """Structured token summary for GuideBuilder.

    Contains aggregated information about tokens to help
    the model understand room labeling patterns.
    """
    total_text_blocks: int
    room_name_candidates: list[RoomNameCandidate] = Field(default_factory=list)
    room_number_candidates: list[RoomNumberCandidate] = Field(default_factory=list)
    high_frequency_numbers: list[HighFrequencyCode] = Field(default_factory=list)
    pairing_pattern: Optional[PairingPattern] = None

    def to_prompt_text(self) -> str:
        """Format summary for inclusion in GuideBuilder prompt."""
        lines = [
            f"Total text blocks: {self.total_text_blocks}",
            "",
            "Room name candidates (uppercase words 2+ chars):",
        ]

        for c in self.room_name_candidates[:10]:  # Top 10
            lines.append(f"  - {c.text}: {c.count} occurrences")

        lines.append("")
        lines.append("Room number candidates (2-4 digit numbers):")

        for c in self.room_number_candidates[:15]:  # Top 15
            if c.near_name:
                lines.append(f"  - {c.text}: near '{c.near_name}' ({c.distance_px}px)")
            else:
                lines.append(f"  - {c.text}: {c.count} occurrences")

        if self.high_frequency_numbers:
            lines.append("")
            lines.append("High-frequency codes (likely noise, consider excluding):")
            for c in self.high_frequency_numbers:
                lines.append(f"  - '{c.text}': {c.count} occurrences ({c.note})")

        if self.pairing_pattern:
            lines.append("")
            lines.append(f"Pairing pattern detected: {self.pairing_pattern.observed_relation}")
            lines.append(f"  Typical distance: {self.pairing_pattern.typical_distance_px[0]}-{self.pairing_pattern.typical_distance_px[1]}px")
            lines.append(f"  Confidence: {self.pairing_pattern.confidence}")
            if self.pairing_pattern.sample_pairs:
                lines.append("  Sample pairs:")
                for name, number in self.pairing_pattern.sample_pairs[:5]:
                    lines.append(f"    - {name} + {number}")

        return "\n".join(lines)


def _bbox_center(bbox: list[int]) -> tuple[int, int]:
    """Get center of bbox [x, y, w, h]."""
    x, y, w, h = bbox
    return x + w // 2, y + h // 2


def _distance(bbox1: list[int], bbox2: list[int]) -> int:
    """Calculate distance between bbox centers."""
    c1 = _bbox_center(bbox1)
    c2 = _bbox_center(bbox2)
    return int(((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5)


def _relative_position(name_bbox: list[int], number_bbox: list[int]) -> str:
    """Determine relative position of number to name."""
    name_cx, name_cy = _bbox_center(name_bbox)
    num_cx, num_cy = _bbox_center(number_bbox)

    dx = num_cx - name_cx
    dy = num_cy - name_cy

    # Threshold for considering something "below" vs "beside"
    if abs(dy) > abs(dx):
        return "number_below_name" if dy > 0 else "number_above_name"
    else:
        return "number_right_of_name" if dx > 0 else "number_left_of_name"


def generate_token_summary(
    tokens: list[TextToken],
    max_pairing_distance: int = 100,
) -> TokenSummary:
    """Generate a structured summary from tokens.

    Args:
        tokens: List of TextToken from any source
        max_pairing_distance: Maximum pixel distance for name-number pairing

    Returns:
        TokenSummary with aggregated statistics
    """
    if not tokens:
        return TokenSummary(total_text_blocks=0)

    # Separate tokens by type
    name_tokens: list[TextToken] = []
    number_tokens: list[TextToken] = []

    # Count occurrences
    name_counts: Counter[str] = Counter()
    number_counts: Counter[str] = Counter()

    for token in tokens:
        text = token.text.strip()

        if ROOM_NAME_PATTERN.match(text):
            name_tokens.append(token)
            name_counts[text] += 1
        elif ROOM_NUMBER_PATTERN.match(text):
            number_tokens.append(token)
            number_counts[text] += 1

    # Build room name candidates (sorted by frequency, then alphabetically)
    room_name_candidates = []
    for text, count in name_counts.most_common(20):
        # Find first occurrence for example bbox
        example = next(t for t in name_tokens if t.text.strip() == text)
        room_name_candidates.append(RoomNameCandidate(
            text=text,
            count=count,
            example_bbox=example.bbox,
        ))

    # Find nearby pairs and build number candidates
    room_number_candidates = []
    pairs: list[tuple[TextToken, TextToken, int]] = []  # (name, number, distance)

    for num_token in number_tokens:
        num_text = num_token.text.strip()

        # Find nearest name token
        nearest_name: Optional[TextToken] = None
        nearest_dist = float("inf")

        for name_token in name_tokens:
            dist = _distance(num_token.bbox, name_token.bbox)
            if dist < nearest_dist and dist <= max_pairing_distance:
                nearest_dist = dist
                nearest_name = name_token

        if nearest_name is not None:
            pairs.append((nearest_name, num_token, int(nearest_dist)))
            room_number_candidates.append(RoomNumberCandidate(
                text=num_text,
                count=number_counts[num_text],
                near_name=nearest_name.text.strip(),
                distance_px=int(nearest_dist),
            ))
        else:
            room_number_candidates.append(RoomNumberCandidate(
                text=num_text,
                count=number_counts[num_text],
            ))

    # Sort by whether they have a nearby name, then by count
    room_number_candidates.sort(key=lambda c: (c.near_name is None, -c.count))
    room_number_candidates = room_number_candidates[:30]  # Limit

    # Detect high-frequency numbers (noise)
    high_frequency_numbers = []
    for text, count in number_counts.items():
        if count >= HIGH_FREQUENCY_THRESHOLD:
            high_frequency_numbers.append(HighFrequencyCode(
                text=text,
                count=count,
                note="likely wall/partition code" if len(text) == 2 else "high frequency",
            ))

    high_frequency_numbers.sort(key=lambda c: -c.count)

    # Detect pairing pattern
    pairing_pattern = None
    if pairs:
        # Analyze position relationships
        positions = Counter()
        distances = []

        for name_tok, num_tok, dist in pairs:
            pos = _relative_position(name_tok.bbox, num_tok.bbox)
            positions[pos] += 1
            distances.append(dist)

        if positions:
            most_common_pos, pos_count = positions.most_common(1)[0]
            total_pairs = len(pairs)

            # Confidence based on consistency
            if pos_count / total_pairs >= 0.7:
                confidence = "high"
            elif pos_count / total_pairs >= 0.5:
                confidence = "medium"
            else:
                confidence = "low"

            # Distance range
            if distances:
                min_dist = min(distances)
                max_dist = max(distances)
                # Use percentiles to avoid outliers
                sorted_dists = sorted(distances)
                p10 = sorted_dists[len(sorted_dists) // 10] if len(sorted_dists) > 10 else min_dist
                p90 = sorted_dists[9 * len(sorted_dists) // 10] if len(sorted_dists) > 10 else max_dist
            else:
                p10, p90 = 0, 100

            # Sample pairs
            sample_pairs = [
                (name.text.strip(), num.text.strip())
                for name, num, _ in pairs[:10]
            ]

            pairing_pattern = PairingPattern(
                observed_relation=most_common_pos,
                typical_distance_px=(p10, p90),
                confidence=confidence,
                sample_pairs=sample_pairs,
            )

    summary = TokenSummary(
        total_text_blocks=len(tokens),
        room_name_candidates=room_name_candidates,
        room_number_candidates=room_number_candidates,
        high_frequency_numbers=high_frequency_numbers,
        pairing_pattern=pairing_pattern,
    )

    logger.info(
        "token_summary_generated",
        total_tokens=len(tokens),
        name_candidates=len(room_name_candidates),
        number_candidates=len(room_number_candidates),
        high_freq_codes=len(high_frequency_numbers),
        has_pairing_pattern=pairing_pattern is not None,
    )

    return summary
