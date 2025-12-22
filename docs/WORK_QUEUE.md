# WORK_QUEUE — Allowed Autonomous Tasks

This file defines what the agent may execute autonomously without asking.
The agent may ONLY work on tasks listed here.

If a task would expand scope, change product phase, or add a new feature not listed here,
the agent MUST stop and ask.

---

## Phase 1 — Build Visual Guide (LOCKED)
Status: LOCKED

No further feature work is allowed in Phase 1.

---

## Phase 1.5 — Hardening for SaaS (COMPLETE)
Status: COMPLETE

No further tasks unless bug fixes.

---

## Phase 2 — Extraction and Query (READY)

Goal: deliver v2 endpoints for object extraction and querying.
Follow docs/FEATURE_ExtractObjects.md and docs/PHASE2_DECISIONS.md.

Allowed autonomous tasks in Phase 2:

1 Page classification
- Implement page_type classifier and persistence.
- Add tests Gate A.

2 Extraction pipeline
- Implement /v2/projects/{id}/extract as async job.
- Steps: classify_pages, extract_objects, build_index.
- Implement status endpoint.

3 Rooms extraction
- Implement conservative room label detection and bbox association.
- Add tests Gate B and Gate C.

4 Doors extraction
- Implement conservative door detection on plan pages.
- Add tests Gate E.

5 Schedule extraction
- Implement schedule page table extraction.
- Add tests Gate F.

6 Project index
- Deterministic ID strategy per PHASE2_DECISIONS.
- Build rooms_by_number and objects_by_type.
- Add tests Gate H.

7 Query endpoint
- Implement query and ambiguity behavior.
- Add tests Gate D.

8 Schema enforcement and failure behavior
- Ensure invalid model output fails loudly.
- Add tests Gate G.

Stop conditions
- If any task requires PDF output or viewer UI, stop and ask.
- If polygons are required to pass gates, stop and ask.

Definition of done
- All tests in TEST_GATES_PHASE2 pass.
- v2 contract matches API_CONTRACT_v2.
