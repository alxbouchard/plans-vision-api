#!/usr/bin/env python3
"""E2E test for token-based room extraction.

This script tests the TokenProvider + TokenBlockAdapter pipeline
directly on PDF files without going through the API.

Usage:
    python scripts/e2e_tokens_test.py
"""

import asyncio
from pathlib import Path
from uuid import uuid4

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.tokens import PyMuPDFTokenProvider, PageRasterSpec
from src.extraction.token_block_adapter import TokenBlockAdapter, SyntheticTextBlock
from src.extraction.spatial_room_labeler import SpatialRoomLabeler
from src.agents.schemas import RulePayload, RuleKind
from src.models.entities import ExtractionPolicy


# Test payloads matching the guide patterns
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


async def test_pdf_extraction(pdf_path: Path, page_number: int, test_name: str):
    """Test token extraction and room labeling on a PDF page."""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"PDF: {pdf_path}")
    print(f"Page: {page_number + 1}")
    print(f"{'='*60}")

    page_id = uuid4()

    # Step 1: Extract tokens with PyMuPDF
    print("\n[Step 1] Extracting tokens with PyMuPDF...")
    provider = PyMuPDFTokenProvider()
    tokens = await provider.get_tokens(
        page_id=page_id,
        pdf_path=pdf_path,
        page_number=page_number,
    )
    print(f"  -> Tokens found: {len(tokens)}")

    if not tokens:
        print("  -> FAIL: No tokens extracted")
        return False

    # Step 2: Create synthetic blocks with TokenBlockAdapter
    print("\n[Step 2] Creating blocks with TokenBlockAdapter...")
    adapter = TokenBlockAdapter(payloads=TEST_PAYLOADS)
    blocks = adapter.create_blocks(tokens, page_id)
    print(f"  -> Blocks created: {len(blocks)}")

    paired_blocks = [b for b in blocks if b.room_number_token]
    name_only_blocks = [b for b in blocks if not b.room_number_token]
    print(f"  -> Paired (name+number): {len(paired_blocks)}")
    print(f"  -> Name only: {len(name_only_blocks)}")

    if not blocks:
        print("  -> FAIL: No blocks created")
        return False

    # Show sample paired blocks
    print("\n  Sample paired blocks:")
    for b in paired_blocks[:10]:
        print(f"    - {b.room_name_token} {b.room_number_token}")

    # Step 3: Pass blocks to SpatialRoomLabeler
    print("\n[Step 3] Running SpatialRoomLabeler...")
    labeler = SpatialRoomLabeler(
        policy=ExtractionPolicy.CONSERVATIVE,
        payloads=TEST_PAYLOADS,
    )

    # Convert SyntheticTextBlock to TextBlockLike (they're compatible)
    rooms = labeler.extract_rooms(
        page_id=page_id,
        text_blocks=blocks,  # SyntheticTextBlock has text_lines property
        door_symbols=[],
    )
    print(f"  -> Rooms emitted: {len(rooms)}")

    if rooms:
        print("\n  Extracted rooms:")
        for room in rooms[:15]:
            print(f"    - {room.room_name} {room.room_number} (conf={room.confidence:.2f})")

    # Verdict
    print(f"\n{'='*60}")
    if len(rooms) > 0:
        print(f"PASS: rooms_emitted = {len(rooms)} > 0")
        return True
    else:
        print(f"FAIL: rooms_emitted = 0")
        return False


async def main():
    """Run E2E tests on both fixtures."""
    results = {}

    # Test 1: Addenda PDF (page 1)
    addenda_pdf = Path("tests/fixtures/23-333 - EJ - Addenda - A-01 - Plans.pdf")
    if addenda_pdf.exists():
        results["addenda_page_1"] = await test_pdf_extraction(
            addenda_pdf, 0, "Addenda Page 1"
        )
    else:
        print(f"\nWARNING: {addenda_pdf} not found")
        results["addenda_page_1"] = False

    # Test 2: Test2 floorplan (page 6 = index 5)
    test2_pdf = Path("tests/fixtures/Test2/Plan architecture construction.pdf")
    if test2_pdf.exists():
        results["test2_page6"] = await test_pdf_extraction(
            test2_pdf, 5, "Test2 Floorplan (Page 6)"
        )
    else:
        print(f"\nWARNING: {test2_pdf} not found")
        results["test2_page6"] = False

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
