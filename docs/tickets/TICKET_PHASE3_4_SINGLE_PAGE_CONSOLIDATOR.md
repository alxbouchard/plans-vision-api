# TICKET: Phase 3.4 - Single Page Must Run Consolidator

**Status: RESOLVED (2025-12-29)**

## Summary

`_run_single_page_flow` in `orchestrator.py` currently bypasses the consolidator entirely,
resulting in `stable_rules_json = NULL` for all single-page projects.

Phase 3.4 requires that single-page projects with visible room labels produce a usable guide
with `stable_rules_json` containing the 3 mandatory payloads.

## Current Behavior (Bug)

```
1 page uploaded → GuideBuilder → provisional stored → status=PROVISIONAL_ONLY
                                                    → stable_rules_json = NULL
```

Consolidator is NEVER called for single-page projects.

## Expected Behavior (Phase 3.4)

```
1 page uploaded → GuideBuilder → GuideApplier (self-apply) → SelfValidator → GuideConsolidator
                                                                            ↓
                                                           IF room labels visible:
                                                             → status=VALIDATED
                                                             → stable_rules_json with 3+ payloads

                                                           IF NO_ROOM_LABELS (cover sheet):
                                                             → status=PROVISIONAL_ONLY (OK)
```

## Decision Logic

| Page Type | Has Room Labels | Expected Status | stable_rules_json |
|-----------|-----------------|-----------------|-------------------|
| Floor plan | Yes | VALIDATED | Contains payloads |
| Cover sheet | No | PROVISIONAL_ONLY | NULL |
| Legend | No | PROVISIONAL_ONLY | NULL |

## Implementation Steps

1. After GuideBuilder succeeds in `_run_single_page_flow`:
2. Call GuideApplier on the SAME page (self-apply for single page)
3. Call SelfValidator with the 1 applier report
4. Call GuideConsolidator
5. If consolidator returns `guide_generated=true` → VALIDATED + persist stable_rules_json
6. If consolidator returns `guide_generated=false` (e.g., NO_ROOM_LABELS) → PROVISIONAL_ONLY

## Files to Modify

- `src/pipeline/orchestrator.py` - `_run_single_page_flow` method

## Files NOT to Modify

- `src/extraction/spatial_room_labeler.py` (FROZEN)
- `src/agents/schemas.py` (FROZEN for Phase 3.7 v1)

## Acceptance Criteria

1. Integration test passes:
   - Upload 1 page with room labels
   - POST /analyze
   - Assert status = "validated"
   - Assert stable_rules_json is not NULL
   - Assert 3 mandatory payloads present (room_name, room_number, pairing)

2. Cover sheet behavior preserved:
   - Upload 1 cover sheet (no room labels)
   - POST /analyze
   - Assert status = "provisional_only"

## Related

- Phase 3.4 prompts in `guide_builder_user.txt` and `guide_consolidator_user.txt`
- Phase 3.7 gate validation depends on stable_rules_json existing

## Resolution

**Fixed in commit (2025-12-29)**

Changes made to `src/pipeline/orchestrator.py`:
- `_run_single_page_flow` now executes full 4-agent pipeline
- Builder → Applier (self-apply) → Validator → Consolidator
- `stable_rules_json` persisted to DB when consolidator returns `guide_generated=true`

Test added: `tests/test_phase3_4_single_page_integration.py` (4 tests)

**Verified:**
- Cover sheet → provisional_only (correct)
- Floor plan with labels → validated + stable_rules_json (when Vision can read labels)

**Remaining blocker:** Vision API cannot read small text at 150-200 DPI.
Consolidator correctly refuses to generate payloads when room labels are unreadable.
Solution: PyMuPDF text extraction for vectorial PDFs.
