"""Adapter to convert separate tokens into text blocks for SpatialRoomLabeler.

Per WORK_QUEUE_PHASE3_5_ROOMS.md:
- PyMuPDF extracts individual words as tokens
- Room labels are often split: "CLASSE" token + "608" token
- This adapter pairs tokens by spatial proximity based on guide payloads
- Produces synthetic TextBlock objects compatible with SpatialRoomLabeler

This is NOT a modification of the frozen SpatialRoomLabeler.
It's a preprocessor that groups tokens into blocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.logging import get_logger
from src.agents.schemas import RulePayload, RuleKind
from .tokens import TextToken, TokenSource

logger = get_logger(__name__)


@dataclass
class AdapterMetrics:
    """Metrics collected during token block creation.

    Used for Phase 3.7 gate validation and debugging.
    """
    tokens_input: int = 0
    room_name_tokens: int = 0
    room_number_tokens: int = 0
    blocks_created: int = 0
    paired_with_number: int = 0
    name_only_no_number: int = 0
    excluded_by_rule: int = 0
    excluded_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def rooms_emitted(self) -> int:
        return self.blocks_created

    @property
    def rooms_with_number(self) -> int:
        return self.paired_with_number

    @property
    def rooms_with_number_ratio(self) -> float:
        if self.blocks_created == 0:
            return 0.0
        return self.paired_with_number / self.blocks_created

    def to_dict(self) -> dict:
        return {
            "tokens_input": self.tokens_input,
            "room_name_tokens": self.room_name_tokens,
            "room_number_tokens": self.room_number_tokens,
            "rooms_emitted": self.rooms_emitted,
            "rooms_with_number": self.rooms_with_number,
            "rooms_with_number_ratio": round(self.rooms_with_number_ratio, 3),
            "name_only_no_number": self.name_only_no_number,
            "excluded_by_rule": self.excluded_by_rule,
            "excluded_reasons": self.excluded_reasons,
        }


class SyntheticTextBlock(BaseModel):
    """A synthetic text block created from paired tokens.

    Compatible with TextBlockLike protocol used by SpatialRoomLabeler.
    """
    bbox: list[int] = Field(min_length=4, max_length=4)
    text: str
    confidence: float = Field(ge=0.0, le=1.0)

    # Metadata for debugging
    room_name_token: Optional[str] = None
    room_number_token: Optional[str] = None
    source_tokens: list[str] = Field(default_factory=list)

    @property
    def text_lines(self) -> list[str]:
        """Return text as lines for SpatialRoomLabeler compatibility."""
        return self.text.split("\n")


def _matches_payload_pattern(text: str, payload: RulePayload) -> bool:
    """Check if text matches the payload's detection pattern."""
    if payload.kind != RuleKind.TOKEN_DETECTOR:
        return False

    if payload.detector == "regex" and payload.pattern:
        try:
            pattern = re.compile(payload.pattern, re.IGNORECASE)
            return bool(pattern.fullmatch(text.strip()))
        except re.error:
            return False

    # Check min_len for letter tokens
    if payload.min_len:
        text_clean = text.strip()
        if len(text_clean) >= payload.min_len:
            # For room_name, check if it's uppercase letters
            if payload.token_type == "room_name":
                return text_clean.isupper() and text_clean.isalpha()
            return True

    return False


def _compute_distance(bbox1: list[int], bbox2: list[int]) -> float:
    """Compute center-to-center distance between two bboxes."""
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2

    cx1 = x1 + w1 / 2
    cy1 = y1 + h1 / 2
    cx2 = x2 + w2 / 2
    cy2 = y2 + h2 / 2

    return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5


def _is_below(name_bbox: list[int], number_bbox: list[int], tolerance: float = 50) -> bool:
    """Check if number_bbox is below name_bbox (with some tolerance)."""
    _, name_y, _, name_h = name_bbox
    _, number_y, _, _ = number_bbox

    # Number should be below name (higher Y value)
    name_bottom = name_y + name_h
    return number_y >= name_y - tolerance


def _union_bbox(bbox1: list[int], bbox2: list[int]) -> list[int]:
    """Compute union of two bboxes."""
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2

    min_x = min(x1, x2)
    min_y = min(y1, y2)
    max_x = max(x1 + w1, x2 + w2)
    max_y = max(y1 + h1, y2 + h2)

    return [min_x, min_y, max_x - min_x, max_y - min_y]


class TokenBlockAdapter:
    """Converts separate tokens into paired text blocks.

    Uses guide payloads to:
    1. Filter tokens by room_name and room_number patterns
    2. Apply exclude rules from guide (Phase 3.7)
    3. Pair them by spatial proximity (below/near relation)
    4. Produce synthetic blocks compatible with SpatialRoomLabeler
    """

    def __init__(
        self,
        payloads: list[RulePayload],
        max_pairing_distance: float = 200.0,
    ):
        self.payloads = payloads
        self.max_pairing_distance = max_pairing_distance
        self.last_metrics: Optional[AdapterMetrics] = None

        # Extract detector payloads
        self.room_name_detectors = [
            p for p in payloads
            if p.kind == RuleKind.TOKEN_DETECTOR and p.token_type == "room_name"
        ]
        self.room_number_detectors = [
            p for p in payloads
            if p.kind == RuleKind.TOKEN_DETECTOR and p.token_type == "room_number"
        ]
        self.pairing_rules = [
            p for p in payloads
            if p.kind == RuleKind.PAIRING
        ]

        # Extract exclude payloads (Phase 3.7)
        self.exclude_rules = [
            p for p in payloads
            if p.kind == RuleKind.EXCLUDE
        ]

        # Get pairing config
        self.pairing_relation = "below"  # default
        self.pairing_max_distance = max_pairing_distance
        for p in self.pairing_rules:
            if p.relation:
                self.pairing_relation = p.relation
            if p.max_distance_px:
                self.pairing_max_distance = float(p.max_distance_px)

    def _matches_exclude_rule(self, text: str) -> Optional[str]:
        """Check if text matches any exclude rule.

        Returns the exclude reason if matched, None otherwise.
        """
        for rule in self.exclude_rules:
            if rule.pattern:
                try:
                    pattern = re.compile(rule.pattern, re.IGNORECASE)
                    if pattern.fullmatch(text.strip()):
                        return rule.reason or "excluded_by_pattern"
                except re.error:
                    pass
        return None

    def create_blocks(
        self,
        tokens: list[TextToken],
        page_id: UUID,
    ) -> list[SyntheticTextBlock]:
        """Create synthetic text blocks from tokens.

        Args:
            tokens: List of text tokens from any source
            page_id: Page identifier for logging

        Returns:
            List of SyntheticTextBlock ready for SpatialRoomLabeler

        Side effect:
            Updates self.last_metrics with detailed metrics for gate validation.
        """
        # Initialize metrics
        metrics = AdapterMetrics(tokens_input=len(tokens))

        if not self.room_name_detectors and not self.room_number_detectors:
            logger.info(
                "token_adapter_no_detectors",
                page_id=str(page_id),
                tokens_count=len(tokens),
            )
            self.last_metrics = metrics
            return []

        # Step 1: Filter tokens by pattern
        room_name_tokens = []
        room_number_tokens = []

        for token in tokens:
            # Try room_name detectors
            for detector in self.room_name_detectors:
                if _matches_payload_pattern(token.text, detector):
                    # Check exclude rules before adding (Phase 3.7)
                    exclude_reason = self._matches_exclude_rule(token.text)
                    if exclude_reason:
                        metrics.excluded_by_rule += 1
                        metrics.excluded_reasons[exclude_reason] = \
                            metrics.excluded_reasons.get(exclude_reason, 0) + 1
                        logger.debug(
                            "token_excluded_by_rule",
                            page_id=str(page_id),
                            token=token.text,
                            reason=exclude_reason,
                        )
                    else:
                        room_name_tokens.append(token)
                    break

            # Try room_number detectors
            for detector in self.room_number_detectors:
                if _matches_payload_pattern(token.text, detector):
                    room_number_tokens.append(token)
                    break

        metrics.room_name_tokens = len(room_name_tokens)
        metrics.room_number_tokens = len(room_number_tokens)

        logger.info(
            "token_adapter_filtered",
            page_id=str(page_id),
            room_name_tokens=len(room_name_tokens),
            room_number_tokens=len(room_number_tokens),
            excluded_by_rule=metrics.excluded_by_rule,
        )

        # Step 2: Pair tokens by proximity
        blocks = []
        used_numbers = set()

        for name_token in room_name_tokens:
            # Find nearest room_number below this name
            best_number = None
            best_distance = float('inf')

            for i, num_token in enumerate(room_number_tokens):
                if i in used_numbers:
                    continue

                distance = _compute_distance(name_token.bbox, num_token.bbox)

                if distance > self.pairing_max_distance:
                    continue

                # Check relation (below)
                if self.pairing_relation == "below":
                    if not _is_below(name_token.bbox, num_token.bbox):
                        continue

                if distance < best_distance:
                    best_distance = distance
                    best_number = (i, num_token)

            # Create block
            if best_number:
                idx, num_token = best_number
                used_numbers.add(idx)

                # Union bbox
                combined_bbox = _union_bbox(name_token.bbox, num_token.bbox)

                # Combined text
                combined_text = f"{name_token.text}\n{num_token.text}"

                # Confidence: min of both (conservative)
                combined_confidence = min(name_token.confidence, num_token.confidence)

                block = SyntheticTextBlock(
                    bbox=combined_bbox,
                    text=combined_text,
                    confidence=combined_confidence,
                    room_name_token=name_token.text,
                    room_number_token=num_token.text,
                    source_tokens=[name_token.text, num_token.text],
                )
                blocks.append(block)
                metrics.paired_with_number += 1

                logger.debug(
                    "token_pair_created",
                    page_id=str(page_id),
                    room_name=name_token.text,
                    room_number=num_token.text,
                    distance=best_distance,
                )

            else:
                # Name without number - still emit as block
                block = SyntheticTextBlock(
                    bbox=list(name_token.bbox),
                    text=name_token.text,
                    confidence=name_token.confidence,
                    room_name_token=name_token.text,
                    room_number_token=None,
                    source_tokens=[name_token.text],
                )
                blocks.append(block)
                metrics.name_only_no_number += 1

                logger.debug(
                    "token_name_only",
                    page_id=str(page_id),
                    room_name=name_token.text,
                )

        metrics.blocks_created = len(blocks)
        self.last_metrics = metrics

        # Log comprehensive metrics for Phase 3.7 gates
        logger.info(
            "token_adapter_metrics",
            page_id=str(page_id),
            rooms_emitted=metrics.rooms_emitted,
            rooms_with_number=metrics.rooms_with_number,
            rooms_with_number_ratio=round(metrics.rooms_with_number_ratio, 3),
            name_only_no_number=metrics.name_only_no_number,
            excluded_by_rule=metrics.excluded_by_rule,
            excluded_reasons=metrics.excluded_reasons,
        )

        return blocks
