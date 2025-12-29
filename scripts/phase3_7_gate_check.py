#!/usr/bin/env python3
"""Phase 3.7 Gate Validation Script.

Validates GATE 7A and 7B with quantitative metrics:
- rooms_emitted: total rooms extracted
- rooms_with_number: rooms with non-null room_number
- rooms_with_number_ratio: percentage
- rejection_breakdown: reasons for exclusions

Usage:
    python scripts/phase3_7_gate_check.py

Requirements:
    - tests/fixtures/23-333 - EJ - Addenda - A-01 - Plans.pdf
    - tests/fixtures/Test2/Plan architecture construction.pdf
"""

import asyncio
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.tokens import PyMuPDFTokenProvider
from src.extraction.token_block_adapter import TokenBlockAdapter, SyntheticTextBlock
from src.extraction.spatial_room_labeler import SpatialRoomLabeler
from src.agents.schemas import RulePayload, RuleKind
from src.models.entities import ExtractionPolicy


@dataclass
class GateResult:
    """Result of a gate validation."""
    fixture_name: str
    rooms_emitted: int
    rooms_with_number: int
    rooms_with_number_ratio: float
    rooms_name_only: int
    rejection_breakdown: dict[str, int]
    max_rooms: int
    min_number_ratio: float
    passed: bool
    failure_reasons: list[str]


# Test payloads - same as e2e_tokens_test.py
TEST_PAYLOADS = [
    RulePayload(
        kind=RuleKind.TOKEN_DETECTOR,
        token_type="room_name",
        detector="regex",
        pattern=r"[A-Z]{2,}",
        min_len=2,
    ),
    RulePayload(
        kind=RuleKind.TOKEN_DETECTOR,
        token_type="room_number",
        detector="regex",
        pattern=r"\d{2,4}",
    ),
    RulePayload(
        kind=RuleKind.PAIRING,
        name_token="room_name",
        number_token="room_number",
        relation="below",
        max_distance_px=200,
    ),
]


async def run_extraction(
    pdf_path: Path,
    page_number: int,
    payloads: list[RulePayload],
) -> tuple[list, dict[str, int]]:
    """Run extraction pipeline and collect metrics.

    Returns:
        Tuple of (rooms, rejection_breakdown)
    """
    page_id = uuid4()
    rejection_breakdown: Counter = Counter()

    # Step 1: Extract tokens
    provider = PyMuPDFTokenProvider()
    tokens = await provider.get_tokens(
        page_id=page_id,
        pdf_path=pdf_path,
        page_number=page_number,
    )

    if not tokens:
        rejection_breakdown["no_tokens_extracted"] = 1
        return [], dict(rejection_breakdown)

    # Step 2: Create blocks with adapter
    adapter = TokenBlockAdapter(payloads=payloads)
    blocks = adapter.create_blocks(tokens, page_id)

    # Track rejection reasons from adapter
    paired_blocks = [b for b in blocks if b.room_number_token]
    name_only_blocks = [b for b in blocks if not b.room_number_token]

    rejection_breakdown["paired_successfully"] = len(paired_blocks)
    rejection_breakdown["name_only_no_number_nearby"] = len(name_only_blocks)

    # Step 3: Run SpatialRoomLabeler
    labeler = SpatialRoomLabeler(
        policy=ExtractionPolicy.CONSERVATIVE,
        payloads=payloads,
    )

    rooms = labeler.extract_rooms(
        page_id=page_id,
        text_blocks=blocks,
        door_symbols=[],
    )

    # Analyze room results
    for room in rooms:
        if room.room_number:
            rejection_breakdown["emitted_with_number"] += 1
        else:
            rejection_breakdown["emitted_name_only"] += 1

        if room.confidence < 0.5:
            rejection_breakdown["low_confidence"] += 1

    return rooms, dict(rejection_breakdown)


def validate_gate(
    fixture_name: str,
    rooms: list,
    rejection_breakdown: dict[str, int],
    max_rooms: int,
    min_number_ratio: float,
) -> GateResult:
    """Validate gate criteria and return result."""

    rooms_emitted = len(rooms)
    rooms_with_number = len([r for r in rooms if r.room_number])
    rooms_name_only = rooms_emitted - rooms_with_number

    if rooms_emitted > 0:
        rooms_with_number_ratio = rooms_with_number / rooms_emitted
    else:
        rooms_with_number_ratio = 0.0

    # Check gate conditions
    failure_reasons = []

    if rooms_emitted == 0:
        failure_reasons.append("REGRESSION: rooms_emitted = 0")

    if rooms_emitted > max_rooms:
        failure_reasons.append(f"TOO_MANY: {rooms_emitted} > {max_rooms}")

    if rooms_with_number_ratio < min_number_ratio:
        failure_reasons.append(
            f"LOW_NUMBER_RATIO: {rooms_with_number_ratio:.0%} < {min_number_ratio:.0%}"
        )

    passed = len(failure_reasons) == 0

    return GateResult(
        fixture_name=fixture_name,
        rooms_emitted=rooms_emitted,
        rooms_with_number=rooms_with_number,
        rooms_with_number_ratio=rooms_with_number_ratio,
        rooms_name_only=rooms_name_only,
        rejection_breakdown=rejection_breakdown,
        max_rooms=max_rooms,
        min_number_ratio=min_number_ratio,
        passed=passed,
        failure_reasons=failure_reasons,
    )


def print_gate_result(result: GateResult) -> None:
    """Print gate result in readable format."""
    status = "✓ PASS" if result.passed else "✗ FAIL"

    print(f"\n{'='*60}")
    print(f"GATE: {result.fixture_name}")
    print(f"{'='*60}")
    print(f"Status: {status}")
    print()
    print("Metrics:")
    print(f"  rooms_emitted:          {result.rooms_emitted}")
    print(f"  rooms_with_number:      {result.rooms_with_number}")
    print(f"  rooms_with_number_ratio: {result.rooms_with_number_ratio:.1%}")
    print(f"  rooms_name_only:        {result.rooms_name_only}")
    print()
    print("Thresholds:")
    print(f"  max_rooms:              {result.max_rooms}")
    print(f"  min_number_ratio:       {result.min_number_ratio:.0%}")
    print()
    print("Rejection Breakdown:")
    for reason, count in sorted(result.rejection_breakdown.items()):
        print(f"  {reason}: {count}")

    if result.failure_reasons:
        print()
        print("Failure Reasons:")
        for reason in result.failure_reasons:
            print(f"  - {reason}")

    print()


def print_json_metrics(results: list[GateResult]) -> None:
    """Print metrics as JSON for programmatic consumption."""
    output = {
        "gates": [
            {
                "fixture": r.fixture_name,
                "passed": r.passed,
                "metrics": {
                    "rooms_emitted": r.rooms_emitted,
                    "rooms_with_number": r.rooms_with_number,
                    "rooms_with_number_ratio": round(r.rooms_with_number_ratio, 3),
                    "rooms_name_only": r.rooms_name_only,
                },
                "thresholds": {
                    "max_rooms": r.max_rooms,
                    "min_number_ratio": r.min_number_ratio,
                },
                "rejection_breakdown": r.rejection_breakdown,
                "failure_reasons": r.failure_reasons,
            }
            for r in results
        ],
        "all_passed": all(r.passed for r in results),
    }
    print("\n" + "="*60)
    print("JSON OUTPUT")
    print("="*60)
    print(json.dumps(output, indent=2))


async def main() -> int:
    """Run gate validations."""
    results = []

    # GATE 7A: Addenda page 1
    addenda_pdf = Path("tests/fixtures/23-333 - EJ - Addenda - A-01 - Plans.pdf")
    if addenda_pdf.exists():
        rooms, breakdown = await run_extraction(addenda_pdf, 0, TEST_PAYLOADS)
        result = validate_gate(
            fixture_name="GATE_7A_Addenda",
            rooms=rooms,
            rejection_breakdown=breakdown,
            max_rooms=60,
            min_number_ratio=0.70,
        )
        results.append(result)
        print_gate_result(result)
    else:
        print(f"\nWARNING: {addenda_pdf} not found - skipping GATE 7A")

    # GATE 7B: Test2 page 6
    test2_pdf = Path("tests/fixtures/Test2/Plan architecture construction.pdf")
    if test2_pdf.exists():
        rooms, breakdown = await run_extraction(test2_pdf, 5, TEST_PAYLOADS)
        result = validate_gate(
            fixture_name="GATE_7B_Test2",
            rooms=rooms,
            rejection_breakdown=breakdown,
            max_rooms=150,
            min_number_ratio=0.50,
        )
        results.append(result)
        print_gate_result(result)
    else:
        print(f"\nWARNING: {test2_pdf} not found - skipping GATE 7B")

    # Print JSON output
    if results:
        print_json_metrics(results)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    all_passed = True
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  {result.fixture_name}: {status}")
        if not result.passed:
            all_passed = False

    if not results:
        print("  No fixtures found - cannot validate gates")
        return 1

    if all_passed:
        print("\nAll gates passed!")
        return 0
    else:
        print("\nSome gates failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
