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

Decision 6 Room Label Rules Are Phase 3.3 Required Extraction Spec

Context:
Phase 3.3 extraction depends on machine executable payloads derived from the Visual Guide.
Rooms cannot be emitted unless the guide contains payloads for:
- token_detector(room_name)
- token_detector(room_number)
- pairing(room_name ↔ room_number)

Decision:
For Phase 3.3, room label conventions are treated as required extraction specification, not optional "nice to have" knowledge.
If room labels are visually present on analyzed pages, the guide MUST include the three payload types above in stable_rules_json.
These rules are allowed to be medium confidence and may be admitted even if their stability_score is below the global stable threshold (minimum 0.5), provided there is visible evidence on the analyzed pages.
The guide must document limitations instead of omitting required payloads.

Implications:
- No hardcoded word lists in code
- All extraction behavior remains data driven from guide payloads
- Fail fast behavior: if required payloads are missing, Phase 3.3 extraction returns zero rooms and logs missing_required_payloads

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
