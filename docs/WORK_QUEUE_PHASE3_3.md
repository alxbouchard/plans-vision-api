# WORK_QUEUE_PHASE3_3.md
Allowed Autonomous Tasks for Phase 3.3 (Spatial Room Labeling)

Goal
Make the API reliably find room labels like "CLASSE 203" without confusing door numbers like "203" or "203-1", using only observable evidence and zero hardcoded semantics.

Non negotiable rules
- No hardcoded semantics (no keywords like "CLASSE", "LOCAL", etc)
- No hardcoded positions (no "top left", "near title block", etc)
- If ambiguous, return ambiguous true and do not choose
- Never invent
- Persist any data the API serves (no in memory only)
- Feature flag required

Scope
- Phase 3.3 is internal extraction improvement for V2
- It may add internal fields to ExtractedRoom, but public API v2 response shape must not change unless explicitly approved

Autonomous ticket list
Ticket 1 Feature flag
- Add ENABLE_PHASE3_3_SPATIAL_LABELING to settings
- Default false
- Unit test for default

Ticket 2 Pipeline hook (no behavior change when flag false)
- Add a single hook point in extraction pipeline for Phase 3.3
- When flag false, zero additional model calls

Ticket 3 TextBlock type
- Define internal TextBlock with bbox and text
- Validation: bbox within image bounds, text non empty

Ticket 4 TextBlockDetector stub + tests
- Create module src/extraction/text_block_detector.py returning []
- Tests: callable, returns list

Ticket 5 TextBlockDetector minimal vision implementation
- One vision call per plan page
- Output strict JSON list of text blocks (bbox + text)
- Hard failure on invalid JSON
- Logging: request_id, project_id, page_id

Ticket 6 Wiring detector behind flag
- Only run on page_type plan
- Tests: detector not called when flag false (mock)

Ticket 7 SpatialRoomLabeler wiring
- Integrate SpatialRoomLabeler with inputs: text_blocks, doors, image dims
- Output: ExtractedRoom with label_bbox and ambiguity fields set

Ticket 8 Gate 1 fixture stays stable
- Keep existing synthetic Gate 1 tests green
- Add test: wiring off when flag false

Ticket 9 Door context feed
- Run DoorExtractor first
- Feed door bboxes and door number tokens to labeler

Ticket 10 Disambiguation evidence rule
- If a numeric token is inside a door neighborhood, do not treat it as room number
- If conflict, mark room ambiguous with ambiguity_reason

Ticket 11 Persist and surface through overlay and index
- Persist extracted rooms and doors like current pipeline
- Overlay returns objects from DB or persisted store
- Index includes rooms_by_number

Ticket 12 E2E test
- Create project
- Upload synthetic fixture pages
- Run extract
- Assert query room_number 203 returns match or ambiguous true (never empty)
- Assert door 203 and 203-1 appear as doors, not rooms

Definition of done
- All Phase 3.3 test gates pass
- No public API schema changes unless approved
- UI demo can show a match for 203 on the Addenda PDF or returns explicit ambiguity with reason
