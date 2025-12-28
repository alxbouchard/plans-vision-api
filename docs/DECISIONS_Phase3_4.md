# DECISIONS_Phase3_4.md
# Single Page Room Extraction

## Decision 1 — Single Page is a Valid Input

A single plan page with visible room labels MUST produce a usable guide with the 3 required payloads.
Multi-page projects increase confidence but are NOT required for extraction to work.

## Decision 2 — Payload Validations are Mandatory

The GuideApplier MUST produce explicit `payload_validations` for each of the 3 room label payloads.
Silent omission is forbidden.
Status must be one of: `confirmed`, `contradicted`, `not_applicable`.

## Decision 3 — Medium Confidence Acceptable for Room Payloads

For the 3 room label payloads (token_detector room_name, token_detector room_number, pairing):
- Stability score >= 0.5 is acceptable
- The 0.8 threshold applies to other rules, not to these mandatory payloads
- If visual evidence exists, payloads MUST be included

## Decision 4 — Incomplete Guide Must Fail Observably

If a plan page has visible room labels but the guide lacks any of the 3 required payloads:
- overall_consistency MUST be "inconsistent"
- rejection_reason MUST explain what is missing
- Log event: missing_required_payloads

## Decision 5 — DPI Independence

Room extraction MUST work regardless of PNG export resolution.
Acceptable DPI range: 150 to 300.
rooms_emitted may vary but MUST NOT be 0 when room labels are visible.

## Frozen Components (inherited from Phase 3.3)

DO NOT MODIFY:
- SpatialRoomLabeler
- RulePayload schema
- tests/test_phase3_3_gates.py
- Decision 6/7/8 in DECISIONS_Phase3_3.md
