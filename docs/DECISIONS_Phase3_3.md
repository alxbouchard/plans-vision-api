# DECISIONS_Phase3_3.md

Decision 1 No keyword semantics
We do not use language keywords (example: CLASSE) to infer room vs door.
We rely on measurable evidence: geometry neighborhood and token patterns.

Decision 2 Ambiguity is a first class outcome
If the system cannot prove a label is a room, it returns ambiguity true instead of guessing.

Decision 3 Minimal vision usage
We add at most one additional vision call per plan page for text block detection, behind a feature flag.

Decision 4 Internal fields allowed
We may add internal fields to ExtractedRoom for better reasoning (label_bbox, ambiguity).
Public API v2 response stays unchanged until explicit approval.

Decision 5 Provisional mode boosts recall carefully
In provisional_only mode we can relax thresholds but only for explicitly labeled objects.

Decision 6 – Mandatory Room Label Payloads (Phase 3.3)

In Phase 3.3, spatial room extraction is strictly driven by the Visual Guide.

A stable guide MUST include the following machine-executable payloads
when room labels are visibly present on a PLAN page:

1. token_detector for room_name
2. token_detector for room_number
3. pairing rule linking room_name and room_number

If any of these payloads are missing:
- Phase 3.3 extraction MUST be considered invalid
- SpatialRoomLabeler MUST NOT attempt recovery or fallback
- rooms_emitted is expected to be 0
- The phase is marked as FAILED

Rationale:
The SpatialRoomLabeler is a frozen execution engine.
All semantic intelligence MUST come from the guide.
Any fallback or hardcoded behavior would break the MCAF principle
and reintroduce hidden logic.

This decision is final for Phase 3.3.
Any change requires an explicit RFC and new test gates.

Decision 7 Phase 3.3 Validation Criteria (FROZEN)

A stable guide is INVALID for Phase 3.3 if it does not include:
- token_detector(room_name)
- token_detector(room_number)
- pairing(room_name ↔ room_number)

Test Gate Criteria (non-negotiable):

GATE A - Guide payloads persisted:
- stable_rules_json contains at least 3 payloads including:
  - 1x token_detector with token_type=room_name
  - 1x token_detector with token_type=room_number
  - 1x pairing

GATE B - Payloads loaded in extraction:
- Log phase3_3_guide_payloads_loaded with payloads_count >= 3

GATE C - Rooms emitted:
- On at least 1 page classified as plan:
- Log phase3_3_spatial_room_labeler_called with rooms_emitted > 0

Phase 3.3 PASS if and only if all 3 gates pass.
Phase 3.3 FAIL if any gate fails.

Decision 8 Frozen Components

The following are FROZEN and must not be modified:
- SpatialRoomLabeler (src/extraction/spatial_room_labeler.py)
- Prompt contracts:
  - guide_builder_user.txt
  - guide_consolidator_user.txt
  - guide_applier_user.txt

Any change to these components requires explicit RFC approval.
