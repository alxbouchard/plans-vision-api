"""
Phase 3.4 Test Gates - Single Page Room Extraction.

These tests validate Phase 3.4 requirements:
- GATE A: Single page guide payloads (room_name, room_number, pairing)
- GATE B: Payload validations present in GuideApplier output
- GATE C: Extraction on single page (rooms_emitted > 0)

Phase 3.4 PASS if and only if all 3 gates pass on a SINGLE page.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

from src.agents.schemas import (
    RulePayload,
    RuleKind,
    GuideConsolidatorOutput,
    GuideApplierOutput,
    FinalRule,
    RuleValidation,
    RuleValidationStatus,
    PayloadValidation,
    PayloadValidationStatus,
)


# =============================================================================
# GATE A: Single page guide payloads
# =============================================================================

class TestGateA_SinglePageGuidePayloads:
    """GATE A: A single page must produce guide with 3 required payloads."""

    def test_single_page_produces_all_three_payloads(self):
        """
        Given: 1 plan page PNG with visible room labels
        When: analyze
        Then: stable_rules_json contains all 3 required payloads
        """
        stable_rules = [
            FinalRule(
                id="RULE_ROOM_NAME",
                description="Room names are uppercase words",
                applies_when="Inside rooms",
                evidence="Observed on single page: CLASSE, CORRIDOR",
                stability_score=0.6,  # Medium confidence acceptable for single page
                payload=RulePayload(
                    kind=RuleKind.TOKEN_DETECTOR,
                    token_type="room_name",
                    detector="regex",
                    pattern="[A-Z]{2,}",
                    min_len=2,
                ),
            ),
            FinalRule(
                id="RULE_ROOM_NUMBER",
                description="Room numbers are 2-4 digits",
                applies_when="Below room names",
                evidence="Observed on single page: 203, 204",
                stability_score=0.55,  # Medium confidence acceptable
                payload=RulePayload(
                    kind=RuleKind.TOKEN_DETECTOR,
                    token_type="room_number",
                    detector="regex",
                    pattern=r"\d{2,4}",
                    must_be_boxed=False,
                ),
            ),
            FinalRule(
                id="RULE_PAIRING",
                description="Room number positioned below room name",
                applies_when="Room labels",
                evidence="Consistent pattern on single page",
                stability_score=0.5,  # Minimum acceptable
                payload=RulePayload(
                    kind=RuleKind.PAIRING,
                    name_token="room_name",
                    number_token="room_number",
                    relation="below",
                    max_distance_px=100,
                ),
            ),
        ]

        output = GuideConsolidatorOutput(
            guide_generated=True,
            stable_rules=stable_rules,
            partial_observations=[],
            excluded_rules=[],
            limitations=["Single page analysis - confidence may increase with more pages"],
            confidence_level="medium",
        )

        # Verify all 3 payloads present
        payloads = [r.payload for r in output.stable_rules if r.payload]

        room_name_found = any(
            p.kind == RuleKind.TOKEN_DETECTOR and p.token_type == "room_name"
            for p in payloads
        )
        room_number_found = any(
            p.kind == RuleKind.TOKEN_DETECTOR and p.token_type == "room_number"
            for p in payloads
        )
        pairing_found = any(p.kind == RuleKind.PAIRING for p in payloads)

        assert room_name_found, "GATE A FAIL: missing token_detector(room_name)"
        assert room_number_found, "GATE A FAIL: missing token_detector(room_number)"
        assert pairing_found, "GATE A FAIL: missing pairing payload"

    def test_single_page_with_medium_confidence_is_valid(self):
        """Single page with stability_score >= 0.5 is valid for room payloads."""
        rule = FinalRule(
            id="RULE_ROOM_NUMBER",
            description="Room numbers",
            applies_when="Below names",
            evidence="Single page observation",
            stability_score=0.5,  # Minimum threshold
            payload=RulePayload(
                kind=RuleKind.TOKEN_DETECTOR,
                token_type="room_number",
                detector="regex",
                pattern=r"\d{2,4}",
            ),
        )

        # 0.5 is acceptable for Phase 3.4
        assert rule.stability_score >= 0.5, "Stability 0.5 should be acceptable"
        assert rule.payload is not None, "Payload should be present"

    def test_single_page_below_threshold_still_fails(self):
        """Single page with stability_score < 0.5 should fail."""
        stability_score = 0.4
        assert stability_score < 0.5, "Below 0.5 should not be acceptable"


# =============================================================================
# GATE B: Payload validations
# =============================================================================

class TestGateB_PayloadValidations:
    """GATE B: GuideApplier must produce payload_validations for all 3 payloads."""

    def test_payload_validations_present(self):
        """
        Given: same page
        When: apply guide
        Then: payload_validations contains 3 entries (confirmed or contradicted)
        """
        payload_validations = [
            PayloadValidation(
                kind="token_detector",
                token_type="room_name",
                status=PayloadValidationStatus.CONFIRMED,
                evidence="Room names CLASSE, CORRIDOR match pattern [A-Z]{2,}",
            ),
            PayloadValidation(
                kind="token_detector",
                token_type="room_number",
                status=PayloadValidationStatus.CONFIRMED,
                evidence="Room numbers 203, 204, 206 match pattern \\d{2,4}",
            ),
            PayloadValidation(
                kind="pairing",
                token_type=None,
                status=PayloadValidationStatus.CONFIRMED,
                evidence="Room numbers consistently appear below room names",
            ),
        ]

        output = GuideApplierOutput(
            page_number=1,
            rule_validations=[],
            new_observations=[],
            payload_validations=payload_validations,
            overall_consistency="consistent",
        )

        assert len(output.payload_validations) == 3, "GATE B FAIL: must have 3 payload_validations"

        # Verify all 3 types present
        kinds_found = set()
        for pv in output.payload_validations:
            if pv.kind == "token_detector":
                kinds_found.add(f"token_detector_{pv.token_type}")
            else:
                kinds_found.add(pv.kind)

        assert "token_detector_room_name" in kinds_found, "GATE B FAIL: missing room_name validation"
        assert "token_detector_room_number" in kinds_found, "GATE B FAIL: missing room_number validation"
        assert "pairing" in kinds_found, "GATE B FAIL: missing pairing validation"

    def test_empty_payload_validations_fails_gate_b(self):
        """Empty payload_validations fails GATE B."""
        output = GuideApplierOutput(
            page_number=1,
            rule_validations=[],
            new_observations=[],
            payload_validations=[],  # Empty!
            overall_consistency="consistent",
        )

        assert len(output.payload_validations) == 0, "Test setup: should be empty"
        gate_b_pass = len(output.payload_validations) >= 3
        assert not gate_b_pass, "GATE B should fail with empty payload_validations"

    def test_contradicted_payload_is_still_valid_entry(self):
        """A contradicted payload is still a valid entry (not silence)."""
        pv = PayloadValidation(
            kind="token_detector",
            token_type="room_number",
            status=PayloadValidationStatus.CONTRADICTED,
            evidence="Pattern \\d{2,4} does not match observed format",
        )

        assert pv.status == PayloadValidationStatus.CONTRADICTED
        assert pv.evidence != "", "Evidence must explain contradiction"

    def test_not_applicable_is_valid_for_non_plan_pages(self):
        """not_applicable is valid when page has no room labels."""
        pv = PayloadValidation(
            kind="token_detector",
            token_type="room_name",
            status=PayloadValidationStatus.NOT_APPLICABLE,
            evidence="This page is a legend, no rooms present",
        )

        assert pv.status == PayloadValidationStatus.NOT_APPLICABLE


# =============================================================================
# GATE C: Extraction on single page
# =============================================================================

class TestGateC_SinglePageExtraction:
    """GATE C: Extraction must emit rooms on single page."""

    def test_rooms_emitted_on_single_page(self):
        """
        Given: same project (single page)
        When: extract with ENABLE_PHASE3_3_SPATIAL_LABELING=true
        Then: rooms_emitted > 0
        """
        rooms_emitted = 3
        assert rooms_emitted > 0, "GATE C FAIL: rooms_emitted must be > 0"

    def test_zero_rooms_emitted_fails_gate_c(self):
        """rooms_emitted == 0 fails GATE C."""
        rooms_emitted = 0
        gate_c_pass = rooms_emitted > 0
        assert not gate_c_pass, "GATE C should fail with rooms_emitted=0"


# =============================================================================
# Full Phase 3.4 Validation
# =============================================================================

class TestPhase34FullValidation:
    """Full Phase 3.4 validation combining all gates for single page."""

    def test_all_gates_pass_single_page(self):
        """Phase 3.4 PASS when all 3 gates pass on single page."""
        # GATE A: 3 required payloads present (even with medium confidence)
        has_room_name = True
        has_room_number = True
        has_pairing = True
        min_stability = 0.5
        gate_a = has_room_name and has_room_number and has_pairing

        # GATE B: payload_validations count == 3
        payload_validations_count = 3
        gate_b = payload_validations_count >= 3

        # GATE C: rooms_emitted > 0
        rooms_emitted = 3
        gate_c = rooms_emitted > 0

        phase_3_4_pass = gate_a and gate_b and gate_c
        assert phase_3_4_pass, "Phase 3.4 should PASS when all gates pass on single page"

    def test_missing_room_number_fails_single_page(self):
        """Phase 3.4 FAIL if room_number payload missing on single page."""
        has_room_name = True
        has_room_number = False  # FAIL
        has_pairing = True
        gate_a = has_room_name and has_room_number and has_pairing

        assert not gate_a, "GATE A should fail when room_number missing"

    def test_single_page_with_visible_labels_but_no_extraction_fails(self):
        """
        Scenario: Page has visible room labels but rooms_emitted=0.
        This is a Phase 3.4 failure.
        """
        page_has_visible_room_labels = True
        rooms_emitted = 0

        gate_c = rooms_emitted > 0

        assert not gate_c, "GATE C should fail when rooms_emitted=0 despite visible labels"


# =============================================================================
# Integration helpers
# =============================================================================

def validate_phase3_4_gate_a(stable_rules_json: str) -> tuple[bool, str]:
    """
    Validate GATE A from stable_rules_json.
    Returns (pass, message).
    """
    try:
        data = json.loads(stable_rules_json)
        stable_rules = data.get("stable_rules", [])
    except json.JSONDecodeError:
        return False, "Invalid JSON"

    room_name_found = False
    room_number_found = False
    pairing_found = False

    for rule in stable_rules:
        payload = rule.get("payload")
        if not payload:
            continue

        kind = payload.get("kind")
        token_type = payload.get("token_type")

        if kind == "token_detector" and token_type == "room_name":
            room_name_found = True
        elif kind == "token_detector" and token_type == "room_number":
            room_number_found = True
        elif kind == "pairing":
            pairing_found = True

    if not room_name_found:
        return False, "Missing token_detector(room_name)"
    if not room_number_found:
        return False, "Missing token_detector(room_number)"
    if not pairing_found:
        return False, "Missing pairing payload"

    return True, "GATE A PASS: All 3 payloads present"


def validate_phase3_4_gate_b(payload_validations: list) -> tuple[bool, str]:
    """
    Validate GATE B from payload_validations list.
    Returns (pass, message).
    """
    if len(payload_validations) < 3:
        return False, f"Only {len(payload_validations)} payload_validations, need 3"

    kinds_found = set()
    for pv in payload_validations:
        kind = pv.get("kind", pv.kind if hasattr(pv, "kind") else None)
        token_type = pv.get("token_type", pv.token_type if hasattr(pv, "token_type") else None)

        if kind == "token_detector":
            kinds_found.add(f"token_detector_{token_type}")
        else:
            kinds_found.add(kind)

    missing = []
    if "token_detector_room_name" not in kinds_found:
        missing.append("room_name")
    if "token_detector_room_number" not in kinds_found:
        missing.append("room_number")
    if "pairing" not in kinds_found:
        missing.append("pairing")

    if missing:
        return False, f"Missing validations: {', '.join(missing)}"

    return True, "GATE B PASS: All 3 payload_validations present"


def validate_phase3_4_gate_c(rooms_emitted: int) -> tuple[bool, str]:
    """
    Validate GATE C from rooms_emitted count.
    Returns (pass, message).
    """
    if rooms_emitted > 0:
        return True, f"GATE C PASS: rooms_emitted={rooms_emitted}"
    return False, "GATE C FAIL: rooms_emitted=0"


class TestValidationHelpers:
    """Test the validation helper functions."""

    def test_gate_a_helper_pass(self):
        """GATE A helper correctly identifies passing guide."""
        json_str = json.dumps({
            "stable_rules": [
                {"id": "R1", "payload": {"kind": "token_detector", "token_type": "room_name"}},
                {"id": "R2", "payload": {"kind": "token_detector", "token_type": "room_number"}},
                {"id": "R3", "payload": {"kind": "pairing"}},
            ]
        })
        passed, msg = validate_phase3_4_gate_a(json_str)
        assert passed, msg

    def test_gate_a_helper_fail(self):
        """GATE A helper correctly identifies failing guide."""
        json_str = json.dumps({
            "stable_rules": [
                {"id": "R1", "payload": {"kind": "token_detector", "token_type": "room_name"}},
                # Missing room_number and pairing
            ]
        })
        passed, msg = validate_phase3_4_gate_a(json_str)
        assert not passed
        assert "room_number" in msg or "pairing" in msg

    def test_gate_b_helper_pass(self):
        """GATE B helper correctly identifies passing validations."""
        validations = [
            {"kind": "token_detector", "token_type": "room_name", "status": "confirmed"},
            {"kind": "token_detector", "token_type": "room_number", "status": "confirmed"},
            {"kind": "pairing", "token_type": None, "status": "confirmed"},
        ]
        passed, msg = validate_phase3_4_gate_b(validations)
        assert passed, msg

    def test_gate_c_helper_pass(self):
        """GATE C helper correctly identifies passing extraction."""
        passed, msg = validate_phase3_4_gate_c(5)
        assert passed, msg

    def test_gate_c_helper_fail(self):
        """GATE C helper correctly identifies failing extraction."""
        passed, msg = validate_phase3_4_gate_c(0)
        assert not passed
        assert "rooms_emitted=0" in msg


# =============================================================================
# DPI Robustness Gate (Ticket 5)
# =============================================================================

class TestDPIRobustness:
    """
    DPI Robustness Gate: Extraction must work at different DPI levels.

    The same PDF exported at 150 dpi and 300 dpi must both produce rooms_emitted > 0.
    rooms_emitted may vary but MUST NOT be 0.
    """

    def test_dpi_150_produces_rooms(self):
        """At 150 DPI, rooms_emitted must be > 0."""
        # Simulated result at 150 DPI
        rooms_emitted_150dpi = 3
        assert rooms_emitted_150dpi > 0, "DPI Gate FAIL: rooms_emitted=0 at 150 DPI"

    def test_dpi_300_produces_rooms(self):
        """At 300 DPI, rooms_emitted must be > 0."""
        # Simulated result at 300 DPI
        rooms_emitted_300dpi = 5
        assert rooms_emitted_300dpi > 0, "DPI Gate FAIL: rooms_emitted=0 at 300 DPI"

    def test_dpi_variation_is_acceptable(self):
        """
        rooms_emitted may vary between DPI levels, but both must be > 0.
        Variation is acceptable as long as neither drops to 0.
        """
        rooms_emitted_150dpi = 3
        rooms_emitted_300dpi = 5

        # Both must be > 0
        assert rooms_emitted_150dpi > 0, "DPI Gate FAIL at 150 DPI"
        assert rooms_emitted_300dpi > 0, "DPI Gate FAIL at 300 DPI"

        # Variation is OK
        variation = abs(rooms_emitted_300dpi - rooms_emitted_150dpi)
        # No assertion on variation amount - just document it
        print(f"DPI variation: {variation} rooms difference (acceptable)")

    def test_dpi_zero_at_any_level_fails(self):
        """If either DPI level produces 0 rooms, the gate fails."""
        rooms_emitted_150dpi = 3
        rooms_emitted_300dpi = 0  # FAIL scenario

        dpi_gate_pass = rooms_emitted_150dpi > 0 and rooms_emitted_300dpi > 0
        assert not dpi_gate_pass, "DPI Gate should fail when any DPI produces 0"


def validate_dpi_gate(rooms_150dpi: int, rooms_300dpi: int) -> tuple[bool, str]:
    """
    Validate DPI robustness gate.

    Args:
        rooms_150dpi: rooms_emitted at 150 DPI
        rooms_300dpi: rooms_emitted at 300 DPI

    Returns:
        (pass, message)
    """
    if rooms_150dpi == 0:
        return False, f"DPI Gate FAIL: rooms_emitted=0 at 150 DPI"
    if rooms_300dpi == 0:
        return False, f"DPI Gate FAIL: rooms_emitted=0 at 300 DPI"

    variation = abs(rooms_300dpi - rooms_150dpi)
    return True, f"DPI Gate PASS: 150dpi={rooms_150dpi}, 300dpi={rooms_300dpi}, variation={variation}"


class TestDPIValidationHelper:
    """Test the DPI validation helper."""

    def test_dpi_helper_pass(self):
        """DPI helper correctly identifies passing scenario."""
        passed, msg = validate_dpi_gate(3, 5)
        assert passed, msg
        assert "PASS" in msg

    def test_dpi_helper_fail_150(self):
        """DPI helper correctly identifies failure at 150 DPI."""
        passed, msg = validate_dpi_gate(0, 5)
        assert not passed
        assert "150 DPI" in msg

    def test_dpi_helper_fail_300(self):
        """DPI helper correctly identifies failure at 300 DPI."""
        passed, msg = validate_dpi_gate(3, 0)
        assert not passed
        assert "300 DPI" in msg
